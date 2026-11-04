"""No-cost-by-default EODHD read gate: independent from the AION Worker."""
import unittest
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from atlasquant_trader_calendar_quota_guard import (
    _reset_for_tests, configured_cap, guarded_read,
    permission_enabled, quota_snapshot,
)
from atlasquant_trader_calendar_service import read_calendar

T0 = datetime(2026, 11, 2, 12, 45, tzinfo=timezone.utc)


def _env(cap=4):
    return {"ATLASQUANT_CALENDAR_EODHD_ENABLED": "1",
            "ATLASQUANT_CALENDAR_MAX_CALLS_PER_DAY": str(cap)}


def _call(fn, at=T0, cap=4, token="LAB_SECRET"):
    return guarded_read(token, "2026-11-02", int(at.timestamp()) // 3600,
                        fetch=fn, at=at, env=_env(cap))


class EconomicCalendarQuotaTests(unittest.TestCase):
    def setUp(self):
        _reset_for_tests()

    def tearDown(self):
        _reset_for_tests()

    def test_disabled_without_explicit_opt_in_no_call(self):
        calls = []
        def fetch(*args):
            calls.append(args)
            return {"ok": True, "data": []}
        answer = guarded_read("EXISTS", "2026-11-02", int(T0.timestamp()) // 3600,
                              fetch=fetch, at=T0, env={})
        self.assertEqual(answer["reason"], "PROVIDER_NOT_AUTHORIZED")
        self.assertEqual(calls, [])
        self.assertFalse(permission_enabled({}))
        self.assertFalse(quota_snapshot(at=T0, env={})["enabled"])

    def test_valid_opt_in_and_configured_bounds(self):
        self.assertTrue(permission_enabled(_env()))
        self.assertFalse(permission_enabled({"ATLASQUANT_CALENDAR_EODHD_ENABLED": "not-on"}))
        self.assertEqual(configured_cap({}), 4)
        self.assertEqual(configured_cap(_env(30)), 8)
        self.assertEqual(configured_cap(_env(-2)), 1)
        self.assertEqual(configured_cap({"ATLASQUANT_CALENDAR_MAX_CALLS_PER_DAY": "NaN"}), 4)

    def test_one_fetch_per_hour_and_cap_is_fail_closed(self):
        count = []
        def fetch(*args):
            count.append(args)
            return {"ok": True, "data": [{"test": True}]}
        self.assertTrue(_call(fetch, cap=1)["ok"])
        self.assertTrue(_call(fetch, at=T0+timedelta(minutes=10), cap=1)["ok"])
        self.assertEqual(len(count), 1)
        denied = _call(fetch, at=T0+timedelta(hours=1), cap=1)
        self.assertEqual(denied["reason"], "ATLASQUANT_DAILY_CAP")
        self.assertEqual(len(count), 1)
        self.assertEqual(quota_snapshot(at=T0, env=_env(1))["used_process"], 1)
        self.assertEqual(quota_snapshot(at=T0, env=_env(1))["remaining_process"], 0)

    def test_provider_failure_consumes_slot_without_retry_storm(self):
        calls = []
        def failing(*args):
            calls.append(args)
            raise RuntimeError("sensitive credentials must not leak")
        first = _call(failing, cap=1)
        second = _call(failing, cap=1)
        self.assertEqual(first["reason"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(second["reason"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("sensitive", str(first))
        self.assertEqual(_call(failing, at=T0+timedelta(hours=1), cap=1)["reason"],
                         "ATLASQUANT_DAILY_CAP")

    def test_daily_reset_uses_utc_provider_boundary(self):
        at = datetime(2026, 11, 2, 23, 40, tzinfo=timezone.utc)
        fetches = []
        def fetch(*args):
            fetches.append(args)
            return {"ok": True, "data": []}
        self.assertTrue(_call(fetch, at=at, cap=1)["ok"])
        next_day = at + timedelta(hours=1)
        self.assertTrue(_call(fetch, at=next_day, cap=1)["ok"])
        self.assertEqual(len(fetches), 2)
        self.assertEqual(quota_snapshot(at=next_day, env=_env(1))["used_process"], 1)

    def test_concurrent_identical_request_spends_at_most_one_slot(self):
        calls = []
        def fetch(*args):
            calls.append(args)
            return {"ok": True, "data": []}
        with ThreadPoolExecutor(max_workers=12) as pool:
            answers = list(pool.map(lambda _: _call(fetch, cap=1), range(12)))
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(x["ok"] for x in answers))
        self.assertEqual(quota_snapshot(at=T0, env=_env(1))["used_process"], 1)

    def test_secret_never_in_provider_error_or_snapshot(self):
        def fail(*args):
            return {"ok": False, "reason": "HTTP_403", "data": []}
        raw = _call(fail, token="sk_THIS_IS_PRIVATE", cap=1)
        self.assertNotIn("sk_THIS_IS_PRIVATE", str(raw))
        self.assertNotIn("sk_THIS_IS_PRIVATE", str(quota_snapshot(at=T0, env=_env(1))))

    def test_authenticated_streamlit_remains_off_even_if_secret_exists(self):
        class Fake:
            secrets = {}
            session_state = {}
        st = Fake()
        access = {"allowed": True, "role": "ADMIN", "username": "owner"}
        with patch.dict("os.environ", {
                "CHAVE_EODHD": "EXISTING_SECRET",
                "ATLASQUANT_CALENDAR_EODHD_ENABLED": "0"}, clear=False):
            with patch("atlasquant_trader_calendar_service._hourly_feed") as source:
                model = read_calendar(st, access, at=T0)
                self.assertEqual(model["state"], "UNAVAILABLE")
                self.assertEqual(model["reason"], "PROVIDER_NOT_AUTHORIZED")
                source.assert_not_called()


if __name__ == "__main__":
    unittest.main()
