"""Fail-closed contracts for official indicative ECB reference history."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import unittest

from atlasquant_trader_ecb_eurusd_reference_history_lab import (
    SCHEMA, SOURCE_URL, inspect_ecb_eurusd_reference_history_lab as inspect,
)

CAPTURE = datetime(2026, 11, 5, 0, 30, tzinfo=timezone.utc)
AS_OF = datetime(2026, 11, 5, 1, 0, tzinfo=timezone.utc)


def xml(*, days=("2026-11-04", "2026-11-03", "2026-11-02"),
        rates=("1.1267", "1.1179", "1.1216"),
        last_currency="JPY", duplicated_usd=False) -> bytes:
    body = ""
    for day, value in zip(days, rates):
        body += (f'<Cube time="{day}"><Cube currency="USD" rate="{value}"/>'
                 f'<Cube currency="{last_currency}" rate="178.30"/>')
        if duplicated_usd:
            body += '<Cube currency="USD" rate="1.2"/>'
        body += '</Cube>'
    return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" '
            f'xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">'
            f'<gesmes:subject>Reference rates</gesmes:subject>'
            f'<gesmes:Sender><gesmes:name>European Central Bank</gesmes:name>'
            f'</gesmes:Sender><Cube>{body}</Cube></gesmes:Envelope>').encode()


_UNSET = object()


def run(raw=_UNSET, **kwargs):
    args = dict(captured_at_utc=CAPTURE, as_of_utc=AS_OF,
                requested_start_date="2026-11-02",
                requested_end_date="2026-11-04")
    args.update(kwargs)
    return inspect(xml() if raw is _UNSET else raw, **args)


class EcbReferenceHistoryTests(unittest.TestCase):
    def test_realistic_xml_is_reference_only(self):
        raw = xml()
        r = run(raw)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["source_url"], SOURCE_URL)
        self.assertEqual(r["state"], "LAB_ECB_EURUSD_DAILY_REFERENCE_CONTEXT_ONLY")
        self.assertEqual(r["source_raw_sha256"], sha256(raw).hexdigest())
        self.assertEqual(r["observation_count"], 3)
        self.assertEqual(r["first_observation_date"], "2026-11-02")
        self.assertEqual(r["last_observation_date"], "2026-11-04")
        self.assertEqual(r["start_reference_rate"], "1.1216")
        self.assertEqual(r["end_reference_rate"], "1.1267")
        self.assertEqual(r["quoted_unit"], "USD_PER_1_EUR")

    def test_no_operational_flag_or_return_on_success_or_failure(self):
        for r in (run(), run(b"bad data")):
            for flag in ("trade_authorized", "can_feed_live_radar", "publishable",
                         "worker_enabled", "scheduler_enabled", "intraday_m15_price",
                         "tradable_quote", "independent_execution_price_verified",
                         "historical_point_in_time_eligible",
                         "publication_instant_independently_verified",
                         "archived_historical_vintage_independently_verified"):
                self.assertIs(r[flag], False, flag)
            self.assertIs(r["fx_bias"], None)
            self.assertIs(r["reference_rate_change_pct"], None)
            self.assertEqual(r["operational_bias"], "AGUARDAR")
            self.assertEqual(r["new_cost_brl"], 0)

    def test_missing_requested_day_is_not_backfilled(self):
        r = run(requested_start_date="2026-11-01")
        self.assertEqual(r["reason"], "REQUESTED_DAILY_FIXING_MISSING_NO_FORWARD_FILL")
        self.assertIsNone(r["start_reference_rate"])

    def test_weekend_not_interpolated(self):
        r = run(requested_start_date="2026-10-31")
        self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_reject_naive_and_reversed_capture_times(self):
        for args in (
            dict(captured_at_utc=datetime(2026, 11, 5)),
            dict(as_of_utc=datetime(2026, 11, 5)),
            dict(as_of_utc=CAPTURE - timedelta(seconds=1)),
            dict(as_of_utc="2026-11-05"),
            dict(captured_at_utc=None),
        ):
            with self.subTest(args=args):
                self.assertEqual(run(**args)["state"], "LAB_BLOCKED")

    def test_reject_future_or_reversed_requested_horizons(self):
        for args in (
            dict(requested_start_date="2026-11-04", requested_end_date="2026-11-02"),
            dict(requested_start_date="2026-11-04", requested_end_date="2026-11-04"),
            dict(requested_end_date="2026-11-06"),
            dict(requested_start_date="2026-11-2"),
            dict(requested_start_date="2026-02-30"),
            dict(requested_start_date=None),
        ):
            with self.subTest(args=args):
                self.assertEqual(run(**args)["reason"], "INVALID_CAPTURE_OR_DATE_BOUNDARY")

    def test_reject_captured_after_requested_historical_asof(self):
        self.assertEqual(
            run(as_of_utc=datetime(2026, 10, 30, tzinfo=timezone.utc))["state"],
            "LAB_BLOCKED")

    def test_reject_latest_xml_observation_after_capture(self):
        self.assertEqual(run(xml(days=("2026-11-06", "2026-11-04", "2026-11-02")))["state"],
                         "LAB_BLOCKED")

    def test_reject_duplicate_or_unsorted_dates(self):
        for days in (("2026-11-04", "2026-11-04", "2026-11-02"),
                     ("2026-11-02", "2026-11-03", "2026-11-04")):
            self.assertEqual(run(xml(days=days))["state"], "LAB_BLOCKED")

    def test_reject_weekend_in_payload(self):
        self.assertEqual(run(xml(days=("2026-11-04", "2026-10-31", "2026-11-02")))["state"],
                         "LAB_BLOCKED")

    def test_reject_duplicate_currency_per_day(self):
        self.assertEqual(run(xml(duplicated_usd=True))["state"], "LAB_BLOCKED")

    def test_reject_missing_usd_without_inventing_a_rate(self):
        raw = xml().replace(b'currency="USD"', b'currency="GBP"')
        self.assertEqual(run(raw)["reason"], "USD_RATE_MISSING")

    def test_reject_malformed_rate_forms(self):
        for form in ("-", "NaN", "Infinity", "1,2", "1e2", "0", "-1",
                     "999999", "1.2.3", "", " 1.2", "+1.2"):
            with self.subTest(form=form):
                self.assertEqual(run(xml(rates=(form, "1.1179", "1.1216")))["state"],
                                 "LAB_BLOCKED")

    def test_reject_malformed_unrelated_currency_rate(self):
        self.assertEqual(run(xml().replace(b'rate="178.30"', b'rate="NaN"'))["state"],
                         "LAB_BLOCKED")

    def test_reject_mixed_namespaces_or_fake_sender(self):
        for replacement in (
            (b'European Central Bank', b'Unknown Source'),
            (b'http://www.ecb.int/vocabulary/2002-08-01/eurofxref', b'urn:fake'),
            (b'Reference rates', b'Buy EUR Now'),
        ):
            self.assertEqual(run(xml().replace(*replacement))["state"], "LAB_BLOCKED")

    def test_reject_dtd_and_entity(self):
        for fragment in (b'<!DOCTYPE attack>', b'<!ENTITY boom "X">'):
            self.assertEqual(run(xml() + fragment)["state"], "LAB_BLOCKED")

    def test_reject_invalid_type_or_size(self):
        for raw in (None, "not bytes", b"", b"x" * 300001):
            self.assertEqual(run(raw)["state"], "LAB_BLOCKED")

    def test_reject_incorrect_currency_and_invalid_day(self):
        self.assertEqual(run(xml(last_currency="eur"))["state"], "LAB_BLOCKED")
        self.assertEqual(run(xml(days=("2026-11-04", "2026-11-03", "2026-13-02")))["state"],
                         "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
