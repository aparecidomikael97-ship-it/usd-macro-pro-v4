"""Strict lab reconciliation fixtures, not original ECB response bytes."""
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_ecb_g8_xml_transcript_reconciliation_lab import (
    CURRENCIES_TO_COMPARE,
    reconcile_ecb_g8_xml_against_transcript_lab as reconcile,
)
from atlasquant_trader_ecb_g8_three_day_reference_moves_lab import DAYS
from test_atlasquant_trader_ecb_g8_xml_reference_history_lab import (
    xml, CAPTURE, AS_OF,
)


def run(raw=None, **kwargs):
    params = {
        "raw_xml": xml() if raw is None else raw,
        "captured_at_utc": CAPTURE,
        "as_of_utc": AS_OF,
    }
    params.update(kwargs)
    return reconcile(**params)


class XmlTranscriptReconciliationTests(unittest.TestCase):
    def assert_no_go(self, out):
        for key in (
            "original_xml_origin_authenticated",
            "transcription_independently_authenticated",
            "publication_instant_independently_witnessed",
            "historical_vintage_point_in_time_verified",
            "independent_broker_m15_prices_verified",
            "historical_directional_accuracy_verified",
            "trade_authorized", "can_feed_live_radar", "worker_enabled",
            "scheduler_enabled", "publishable",
        ):
            self.assertIs(out[key], False, key)
        self.assertIsNone(out["fx_bias"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertEqual((out["new_cost_brl"], out["external_http_requests"]), (0, 0))

    def test_frozen_three_days_seven_rates_match_synthetic_fixture(self):
        out = run()
        self.assertEqual(out["state"], "LAB_XML_TRANSCRIPTION_STRUCTURAL_MATCH_UNATTESTED")
        self.assertEqual(out["reference_days"], list(DAYS))
        self.assertEqual(out["reference_currency_count"], 7)
        self.assertEqual(out["expected_reference_cells"], 21)
        self.assertEqual(out["matched_reference_cells"], 21)
        self.assertEqual(out["mismatched_reference_cells"], [])
        self.assertTrue(out["transcription_consistent_with_supplied_xml"])
        self.assertTrue(out["xml_structure_recognized"])
        self.assertEqual(len(out["raw_xml_sha256"]), 64)
        self.assert_no_go(out)

    def test_one_manually_transcribed_mismatch_is_explicitly_blocked(self):
        bad = xml().replace(
            b'<Cube currency="CHF" rate="0.9166"/>',
            b'<Cube currency="CHF" rate="0.9167"/>',
        )
        out = run(bad)
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["matched_reference_cells"], 20)
        self.assertEqual(len(out["mismatched_reference_cells"]), 1)
        self.assertEqual(out["mismatched_reference_cells"][0]["currency"], "CHF")
        self.assertEqual(out["mismatched_reference_cells"][0]["reference_day"], "2026-11-03")
        self.assertEqual(out["reason"], "XML_AND_MANUAL_REFERENCE_DISAGREE_NO_SILENT_REPAIR")
        self.assert_no_go(out)

    def test_all_21_cell_positions_are_compared_individually(self):
        for day in DAYS:
            for currency in CURRENCIES_TO_COMPARE:
                source = xml()
                # Replace the relevant quoted rate within the matching day only.
                # A unique per-day original amount avoids touching other days.
                from atlasquant_trader_ecb_g8_three_day_reference_moves_lab import REFS
                original = REFS[day][currency].encode()
                marker = b'<Cube time="' + day.encode() + b'">'
                head, tail = source.split(marker, 1)
                body, remainder = tail.split(b'</Cube>', 1)
                cell = b'<Cube currency="' + currency.encode() + b'" rate="' + original + b'"/>'
                self.assertIn(cell, body)
                changed_body = body.replace(
                    cell, b'<Cube currency="' + currency.encode() + b'" rate="999.999"/>', 1)
                changed = head + marker + changed_body + b'</Cube>' + remainder
                result = run(changed)
                self.assertEqual(result["state"], "LAB_BLOCKED", (day, currency))
                self.assertEqual(result["matched_reference_cells"], 20)
                self.assertEqual(len(result["mismatched_reference_cells"]), 1)
                self.assertEqual(result["mismatched_reference_cells"][0]["currency"], currency)
                self.assertEqual(result["mismatched_reference_cells"][0]["reference_day"], day)
                self.assert_no_go(result)

    def test_two_mismatches_keep_both_provenance_differences(self):
        bad = xml().replace(
            b'<Cube currency="USD" rate="1.1267"/>',
            b'<Cube currency="USD" rate="1.1268"/>',
        ).replace(
            b'<Cube currency="JPY" rate="176.95"/>',
            b'<Cube currency="JPY" rate="176.96"/>',
        )
        out = run(bad)
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["matched_reference_cells"], 19)
        self.assertEqual(len(out["mismatched_reference_cells"]), 2)
        self.assert_no_go(out)

    def test_missing_earliest_day_denied_without_forward_fill(self):
        out = run(xml(days=DAYS[1:]))
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["matched_reference_cells"], 0)
        self.assertIn("REQUESTED_DAY_MISSING", out["reason"])
        self.assert_no_go(out)

    def test_missing_one_currency_denied_without_synthesis(self):
        out = run(xml(missing=("2026-11-03", "CAD")))
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["matched_reference_cells"], 0)
        self.assertIn("G8_EUR_BASE_QUOTES_MISSING", out["reason"])

    def test_duplicate_currency_denied(self):
        for value in ("JPY", "SEK"):
            self.assertEqual(run(xml(duplicate=value))["state"], "LAB_BLOCKED")

    def test_duplicate_date_denied(self):
        self.assertEqual(
            run(xml(days=("2026-11-04", "2026-11-04", "2026-11-02")))["state"],
            "LAB_BLOCKED",
        )

    def test_html_doctype_and_invalid_bytes_denied(self):
        for value in (b"", b"<html>fake</html>", b'<!DOCTYPE x>' + xml(),
                      b"\xff" + xml(), b"fake"):
            out = run(value)
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assert_no_go(out)

    def test_future_capture_time_denied(self):
        out = run(captured_at_utc=AS_OF + timedelta(days=1))
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assert_no_go(out)

    def test_before_observation_completion_denied(self):
        out = run(captured_at_utc=datetime(2026, 11, 4, 20, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assert_no_go(out)

    def test_naive_asof_and_capture_denied(self):
        for changes in (
            {"captured_at_utc": CAPTURE.replace(tzinfo=None)},
            {"as_of_utc": AS_OF.replace(tzinfo=None)},
        ):
            self.assertEqual(run(**changes)["state"], "LAB_BLOCKED")

    def test_hash_of_a_synthetic_xml_does_not_authenticate_public_origin(self):
        good = run()
        self.assertIsNotNone(good["raw_xml_sha256"])
        self.assertFalse(good["original_xml_origin_authenticated"])
        self.assertFalse(good["historical_vintage_point_in_time_verified"])
        self.assert_no_go(good)

    def test_deterministic_reconciliation_does_not_call_the_internet(self):
        self.assertEqual(run(), run())
        self.assertEqual(run()["external_http_requests"], 0)


if __name__ == "__main__":
    unittest.main()
