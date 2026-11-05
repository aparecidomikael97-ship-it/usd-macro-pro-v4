"""Synthetic ECB XML response contracts; no original HTTP or PIT evidence."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_ecb_g8_xml_reference_history_lab import (
    SCHEMA, SOURCE_URL, inspect_ecb_g8_xml_reference_history_lab as inspect,
)
from atlasquant_trader_ecb_g8_three_day_reference_moves_lab import REFS

AS_OF = datetime(2026, 11, 5, 6, tzinfo=timezone.utc)
CAPTURE = datetime(2026, 11, 5, 5, tzinfo=timezone.utc)
DAYS = ("2026-11-02", "2026-11-03", "2026-11-04")


def xml(*, days=DAYS, missing=None, duplicate=None, malformed_rate=None,
        other_currency="SEK", extra_eur=False) -> bytes:
    body = []
    for day in reversed(days):
        quotes = REFS.get(day, REFS["2026-11-04"])
        leaves = []
        for cur in ("USD", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD"):
            if missing == (day, cur):
                continue
            price = "NaN" if malformed_rate == (day, cur) else quotes[cur]
            leaves.append(f'<Cube currency="{cur}" rate="{price}"/>')
        leaves.append(f'<Cube currency="{other_currency}" rate="10.2500"/>')
        if duplicate is not None:
            leaves.append(f'<Cube currency="{duplicate}" rate="2.0"/>')
        if extra_eur:
            leaves.append('<Cube currency="EUR" rate="1"/>')
        body.append(f'<Cube time="{day}">{"".join(leaves)}</Cube>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" '
        'xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">'
        '<gesmes:subject>Reference rates</gesmes:subject>'
        '<gesmes:Sender><gesmes:name>European Central Bank</gesmes:name></gesmes:Sender>'
        '<Cube>' + ''.join(body) + '</Cube></gesmes:Envelope>'
    ).encode("utf-8")


def run(raw=None, **kw):
    options = {
        "captured_at_utc": CAPTURE,
        "as_of_utc": AS_OF,
        "requested_dates": list(DAYS),
    }
    options.update(kw)
    return inspect(xml() if raw is None else raw, **options)


def pair(report, symbol):
    return next(row for row in report["pairs"] if row["pair"] == symbol)


class EcbG8XmlReaderTests(unittest.TestCase):
    def assert_research_only(self, out):
        for field in (
            "xml_bytes_original_http_origin_authenticated",
            "official_publication_instant_independently_attested",
            "archived_point_in_time_vintage_verified",
            "independent_broker_m15_prices_verified",
            "licensing_for_commercial_market_data_verified",
            "historical_accuracy_verified",
            "trade_authorized", "can_feed_live_radar", "publishable",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertIs(out[field], False, field)
        self.assertIsNone(out["currency_strength_rank"])
        self.assertIsNone(out["fx_bias"])
        self.assertEqual((out["D1"], out["W1"]), ("AGUARDAR", "AGUARDAR"))
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))
        for row in out["pairs"]:
            self.assertIsNone(row["currency_strength_rank"])
            self.assertIsNone(row["fx_bias"])
            self.assertFalse(row["trade_authorized"])
            self.assertFalse(row["forecast_existed_before_move_attested"])
            self.assertFalse(row["prices_are_executable"])

    def test_three_day_original_shape_fixture_covers_28_crosses(self):
        raw = xml()
        report = run(raw)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["source_url"], SOURCE_URL)
        self.assertEqual(report["state"],
                         "LAB_G8_XML_REFERENCE_CROSSES_STRUCTURALLY_PARSED_UNATTESTED")
        self.assertEqual((report["currency_count"], report["pair_count"]), (8, 28))
        self.assertEqual(report["xml_observation_count"], 3)
        self.assertEqual(report["observed_interval_count"], 56)
        self.assertEqual(report["source_raw_sha256"], sha256(raw).hexdigest())
        self.assertEqual(report["source_bytes"], len(raw))
        self.assertEqual(report["requested_dates"], list(DAYS))
        self.assertTrue(report["xml_structure_verified"])
        self.assertEqual({row["pair"] for row in report["pairs"]}, set(OFFICIAL_PAIRS))
        self.assert_research_only(report)

    def test_crosses_match_only_manual_reference_arithmetic_not_real_feed(self):
        report = run()
        for row in report["pairs"]:
            base, quote = row["pair"].split("/")
            for day in DAYS:
                expected = Decimal(REFS[day][quote]) / Decimal(REFS[day][base])
                observed = Decimal(row["reference_rates_derived_from_ecb_eur_legs"][day])
                self.assertLessEqual(abs(observed - expected), Decimal("0.000000005"))

    def test_eur_usd_reference_follows_three_days(self):
        report = run()
        vals = pair(report, "EUR/USD")["reference_rates_derived_from_ecb_eur_legs"]
        self.assertEqual(vals, {
            "2026-11-02": "1.12160000", "2026-11-03": "1.11790000",
            "2026-11-04": "1.12670000",
        })
        self.assert_research_only(report)

    def test_eur_usd_observed_fall_then_rise_never_predictive(self):
        moves = pair(run(), "EUR/USD")["observed_reference_moves_percent"]
        self.assertLess(Decimal(moves["2026-11-02_to_2026-11-03"]), 0)
        self.assertGreater(Decimal(moves["2026-11-03_to_2026-11-04"]), 0)

    def test_usd_jpy_orientation_cannot_invert(self):
        x = pair(run(), "USD/JPY")
        self.assertEqual(x["unit"], "JPY_PER_1_USD")
        for day in DAYS:
            expected = Decimal(REFS[day]["JPY"]) / Decimal(REFS[day]["USD"])
            value = Decimal(x["reference_rates_derived_from_ecb_eur_legs"][day])
            self.assertLess(abs(value - expected), Decimal("0.000000005"))

    def test_all_56_returns_from_unrounded_legs(self):
        for row in run()["pairs"]:
            base, quote = row["pair"].split("/")
            exact = {day: Decimal(REFS[day][quote]) / Decimal(REFS[day][base])
                     for day in DAYS}
            for first, second in zip(DAYS, DAYS[1:]):
                expected = (exact[second] / exact[first] - 1) * 100
                observed = Decimal(row["observed_reference_moves_percent"][
                    f"{first}_to_{second}"])
                self.assertLessEqual(abs(expected - observed), Decimal("0.00005"))

    def test_two_requested_days_is_valid_subset(self):
        r = run(requested_dates=["2026-11-03", "2026-11-04"])
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual(r["observed_interval_count"], 28)
        self.assertEqual(len(pair(r, "GBP/USD")["observed_reference_moves_percent"]), 1)
        self.assert_research_only(r)

    def test_missing_requested_day_not_backfilled(self):
        r = run(requested_dates=list(DAYS), raw=xml(days=DAYS[1:]))
        self.assertEqual(r["reason"], "REQUESTED_DAY_MISSING_NO_FORWARD_FILL")
        self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_missing_g8_currency_denied_for_requested_day(self):
        r = run(raw=xml(missing=("2026-11-03", "CHF")))
        self.assertEqual(r["reason"], "G8_EUR_BASE_QUOTES_MISSING")
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_research_only(r)

    def test_unrequested_incomplete_day_allowed_but_not_interpolated(self):
        r = run(raw=xml(missing=("2026-11-02", "CAD")),
                requested_dates=["2026-11-03", "2026-11-04"])
        self.assertEqual(r["pair_count"], 28)

    def test_unrelated_currency_is_parsed_without_becoming_ninth_g8(self):
        r = run(raw=xml(other_currency="NOK"))
        self.assertEqual((r["currency_count"], r["pair_count"]), (8, 28))
        self.assert_research_only(r)

    def test_duplicate_g8_or_unrelated_currency_denied(self):
        for currency in ("JPY", "SEK", "USD"):
            r = run(raw=xml(duplicate=currency))
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_eur_as_explicit_quote_denied(self):
        self.assertEqual(run(raw=xml(extra_eur=True))["state"], "LAB_BLOCKED")

    def test_malformed_rate_or_unrelated_malformed_quote_denied(self):
        self.assertEqual(
            run(raw=xml(malformed_rate=("2026-11-04", "JPY")))["state"], "LAB_BLOCKED")
        self.assertEqual(
            run(raw=xml().replace(b'rate="10.2500"', b'rate="NaN"'))["state"], "LAB_BLOCKED")

    def test_invalid_metadata_sender_subject_namespace_denied(self):
        valid = xml()
        for old, new in (
            (b"European Central Bank", b"Other Central Bank"),
            (b"Reference rates", b"Trade Now"),
            (b"http://www.ecb.int/vocabulary/2002-08-01/eurofxref", b"urn:spoofed"),
            (b"http://www.gesmes.org/xml/2002-08-01", b"urn:fake"),
        ):
            self.assertEqual(run(raw=valid.replace(old, new))["state"], "LAB_BLOCKED")

    def test_doctype_and_entity_denied(self):
        for prefix in (b'<!DOCTYPE attack>', b'<!ENTITY x "fake">'):
            self.assertEqual(run(raw=prefix + xml())["state"], "LAB_BLOCKED")

    def test_invalid_size_bad_type_or_corrupt_xml_denied(self):
        for payload in (b"", b"no xml", b"<xml/>", b"\xff" + xml(),
                        "not bytes", {}, b"a" * 400001):
            self.assertEqual(run(raw=payload)["state"], "LAB_BLOCKED")

    def test_duplicate_days_or_ascending_payload_denied(self):
        self.assertEqual(
            run(raw=xml(days=("2026-11-04", "2026-11-04", "2026-11-02")))["state"],
            "LAB_BLOCKED")
        self.assertEqual(
            run(raw=xml(days=tuple(reversed(DAYS))))["state"], "LAB_BLOCKED")

    def test_missing_wrong_or_duplicate_requested_dates_denied(self):
        for days in (["2026-11-02"], ["2026-11-02", "2026-11-02"],
                     ["2026-11-04", "2026-11-03"], ["2026-11-02", "2026-11-07"],
                     ["2026-11-02", "2026-13-04"], ["2026-11-02", None], ["2026-11-02", "2026-11-06"]):
            self.assertEqual(run(requested_dates=days)["state"], "LAB_BLOCKED")

    def test_request_not_public_before_capture_day(self):
        early = datetime(2026, 11, 4, 23, 59, tzinfo=timezone.utc)
        self.assertEqual(run(captured_at_utc=early)["state"], "LAB_BLOCKED")
        self.assertEqual(run(as_of_utc=early)["state"], "LAB_BLOCKED")

    def test_naive_clock_and_capture_after_asof_denied(self):
        for options in (
            {"captured_at_utc": CAPTURE.replace(tzinfo=None)},
            {"as_of_utc": AS_OF.replace(tzinfo=None)},
            {"captured_at_utc": AS_OF + timedelta(seconds=1)},
            {"as_of_utc": None},
        ):
            self.assertEqual(run(**options)["state"], "LAB_BLOCKED")

    def test_source_hash_does_not_certify_official_origin(self):
        raw = xml()
        r = run(raw=raw)
        self.assertEqual(r["source_raw_sha256"], sha256(raw).hexdigest())
        self.assertFalse(r["xml_bytes_original_http_origin_authenticated"])
        self.assertFalse(r["archived_point_in_time_vintage_verified"])
        self.assertFalse(r["independent_broker_m15_prices_verified"])
        self.assertFalse(r["historical_accuracy_verified"])
        self.assertEqual(r["observed_interval_count"], 56)

    def test_original_lookalike_xml_is_still_untrusted_no_accuracy(self):
        r = run()
        self.assertEqual(r["state"],
                         "LAB_G8_XML_REFERENCE_CROSSES_STRUCTURALLY_PARSED_UNATTESTED")
        self.assertFalse(r["historical_accuracy_verified"])
        self.assertIsNone(r["fx_bias"])
        self.assertFalse(r["trade_authorized"])


if __name__ == "__main__":
    unittest.main()
