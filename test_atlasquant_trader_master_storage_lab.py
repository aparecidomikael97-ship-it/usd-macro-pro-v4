"""LAB-only durability, concurrency, period/provenance, and fail-closed tests."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_trader_master_storage_lab import LabMacroLedger, SCHEMA

AT = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)


class DurableMacroLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "macro_lab.sqlite3"
        self.ledger = LabMacroLedger(self.path)
        self.ledger.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def reserve(self, key, *, at=AT, cap=4, provider="EODHD_CALENDAR",
                authorized=True):
        return self.ledger.reserve(provider, key, at, daily_cap=cap,
                                   authorized=authorized)

    def official(self, key="fred:20261102:0640", *, at=AT, provider="FRED"):
        result = self.reserve(key, at=at, provider=provider)
        self.assertEqual(result["state"], "RESERVED")
        self.assertEqual(self.ledger.finish(key, succeeded=True), "SUCCEEDED")

    def test_disabled_default_consumes_nothing(self):
        r = self.ledger.reserve("EODHD_CALENDAR", "calendar:1", AT, daily_cap=4)
        self.assertEqual(r["state"], "DISABLED")
        self.assertFalse(r["reserved"])
        self.assertEqual(self.reserve("calendar:1")["state"], "RESERVED")

    def test_fourth_call_reserved_fifth_denied(self):
        for i in range(4):
            self.assertEqual(self.reserve(f"calendar:{i}")["state"], "RESERVED")
        self.assertEqual(self.reserve("calendar:4")["state"], "CAP_EXHAUSTED")

    def test_concurrent_reservations_from_distinct_connections(self):
        def run(i):
            ledger = LabMacroLedger(self.path)
            return ledger.reserve("EODHD_CALENDAR", f"calendar:parallel:{i}",
                                  AT, daily_cap=3, authorized=True)["state"]
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(run, range(20)))
        self.assertEqual(results.count("RESERVED"), 3)
        self.assertEqual(results.count("CAP_EXHAUSTED"), 17)

    def test_new_instance_same_file_respects_old_budget(self):
        self.reserve("calendar:one", cap=1)
        restarted = LabMacroLedger(self.path)
        denied = restarted.reserve("EODHD_CALENDAR", "calendar:two",
                                   AT, daily_cap=1, authorized=True)
        self.assertEqual(denied["state"], "CAP_EXHAUSTED")

    def test_duplicate_key_cannot_spend_again(self):
        self.reserve("calendar:same", cap=1)
        self.assertEqual(self.reserve("calendar:same", cap=1)["state"], "EXISTS")
        self.assertEqual(self.reserve("calendar:new", cap=1)["state"], "CAP_EXHAUSTED")

    def test_crashed_reservation_stays_spent(self):
        self.reserve("calendar:crash", cap=1)
        self.assertEqual(LabMacroLedger(self.path).reserve(
            "EODHD_CALENDAR", "calendar:retry", AT,
            daily_cap=1, authorized=True)["state"], "CAP_EXHAUSTED")
        self.assertEqual(self.ledger.finish("calendar:crash", succeeded=False),
                         "FAILED")

    def test_failed_api_check_never_creates_observation(self):
        self.reserve("fred:failed", provider="FRED")
        self.assertEqual(self.ledger.finish(
            "fred:failed", succeeded=False, error_code="HTTP_429"), "FAILED")
        with self.assertRaises(ValueError):
            self.ledger.record_observation(
                "fred:failed", provider="FRED", series="US_CPI_YOY",
                economic_period="2026-10", value=3.1, unit="% y/y", origin="FRED")
        read = self.ledger.snapshot("FRED", "US_CPI_YOY")
        self.assertEqual(read["latest_check_status"], "FAILED")
        self.assertEqual(read["latest_error_code"], "HTTP_429")
        self.assertIsNone(read["last_known_value"])
        self.assertIsNone(read["current_display_value"])

    def test_success_with_empty_api_payload_is_not_a_number(self):
        self.official()
        state = self.ledger.snapshot("FRED", "US_UNEMPLOYMENT")
        self.assertEqual(state["latest_check_status"], "SUCCEEDED")
        self.assertEqual(state["status"], "NO_OBSERVATION")
        self.assertIsNone(state["last_known_value"])

    def test_observation_time_period_and_origin_are_distinct(self):
        self.official()
        kind = self.ledger.record_observation(
            "fred:20261102:0640", provider="FRED", series="US_CPI_YOY",
            economic_period="2026-09", value=3.1, unit="% y/y", origin="FRED")
        self.assertEqual(kind, "FIRST_SEEN_PERIOD_NOT_RELEASE_PROOF")
        state = self.ledger.snapshot("FRED", "US_CPI_YOY")
        self.assertEqual(state["economic_period"], "2026-09")
        self.assertEqual(state["observation_checked_at_utc"], AT.isoformat())
        self.assertEqual(state["origin"], "FRED")
        self.assertEqual(state["last_known_value"], 3.1)
        self.assertFalse(state["new_release_confirmed"])
        self.assertIsNone(state["current_display_value"])

    def test_same_value_is_not_a_fresh_disclosure(self):
        self.official()
        kwargs = dict(provider="FRED", series="US_CPI_YOY",
                      economic_period="2026-09", value=3.1,
                      unit="% y/y", origin="FRED")
        self.ledger.record_observation("fred:20261102:0640", **kwargs)
        self.assertEqual(self.ledger.record_observation(
            "fred:20261102:0640", **kwargs), "UNCHANGED_PERIOD")
        self.assertEqual(self.ledger.snapshot("FRED", "US_CPI_YOY")[
            "value_change_kind"], "FIRST_SEEN_PERIOD_NOT_RELEASE_PROOF")

    def test_changed_value_requires_revision_review(self):
        self.official()
        kwargs = dict(provider="FRED", series="US_CPI_YOY",
                      economic_period="2026-09", unit="% y/y", origin="FRED")
        self.ledger.record_observation("fred:20261102:0640", value=3.1, **kwargs)
        self.reserve("fred:revision", provider="FRED", at=AT + timedelta(hours=1))
        self.ledger.finish("fred:revision", succeeded=True)
        self.assertEqual(self.ledger.record_observation(
            "fred:revision", value=3.2, **kwargs),
            "VALUE_CHANGE_UNVERIFIED_REVISION")
        state = self.ledger.snapshot("FRED", "US_CPI_YOY")
        self.assertFalse(state["new_release_confirmed"])
        self.assertEqual(state["last_known_value"], 3.2)

    def test_failure_preserves_history_without_showing_current_value(self):
        self.official()
        self.ledger.record_observation(
            "fred:20261102:0640", provider="FRED", series="US_CPI_YOY",
            economic_period="2026-09", value=3.1, unit="% y/y", origin="FRED")
        self.reserve("fred:later", provider="FRED", at=AT + timedelta(hours=1))
        self.ledger.finish("fred:later", succeeded=False, error_code="HTTP_503")
        state = self.ledger.snapshot("FRED", "US_CPI_YOY")
        self.assertEqual(state["latest_check_status"], "FAILED")
        self.assertEqual(state["last_known_value"], 3.1)
        self.assertIsNone(state["current_display_value"])

    def test_brt_midnight_does_not_reset_utc_account_budget(self):
        before = datetime(2026, 11, 3, 2, 59, tzinfo=timezone.utc)
        after = datetime(2026, 11, 3, 3, 1, tzinfo=timezone.utc)
        self.assertEqual(self.reserve("calendar:before", at=before, cap=1)["state"],
                         "RESERVED")
        self.assertEqual(self.reserve("calendar:after", at=after, cap=1)["state"],
                         "CAP_EXHAUSTED")
        next_day = datetime(2026, 11, 4, 3, 1, tzinfo=timezone.utc)
        self.assertEqual(self.reserve("calendar:next", at=next_day, cap=1)["state"],
                         "RESERVED")

    def test_bad_period_nan_or_origin_fails_without_mutation(self):
        self.official()
        base = dict(request_key="fred:20261102:0640", provider="FRED",
                    series="US_CPI_YOY", economic_period="2026-09",
                    value=3.1, unit="% y/y", origin="FRED")
        for changes in ({"economic_period": "2026-99"},
                        {"economic_period": "2026-12"},
                        {"value": float("nan")},
                        {"value": True},
                        {"origin": "BCB-SGS"},
                        {"series": "NOT SAFE"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.ledger.record_observation(**(base | changes))
        self.assertIsNone(self.ledger.snapshot("FRED", "US_CPI_YOY")[
            "last_known_value"])

    def test_no_implicit_db_or_runner_on_construct(self):
        other = Path(self.tmp.name) / "unused.sqlite3"
        LabMacroLedger(other)
        self.assertFalse(other.exists())
        self.assertEqual(SCHEMA, "ATLASQUANT_MASTER_DURABLE_LAB_V1")


if __name__ == "__main__":
    unittest.main()
