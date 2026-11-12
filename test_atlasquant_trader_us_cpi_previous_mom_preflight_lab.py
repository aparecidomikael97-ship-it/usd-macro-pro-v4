"""US CPI monthly prior-value source preflight; no counterfeit P-I-T history."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import unittest

from atlasquant_trader_us_cpi_previous_mom_preflight_lab import (
    CASEBOOK_SHA256,
    inspect_us_cpi_previous_mom_preflight_lab as inspect,
)

RECEIPT = (Path(__file__).resolve().parent / "docs" / "continuidade" /
           "TRADER_US_CPI_SEPAUG2026_PREVIOUS_MOM_RESEARCH_LAB_20261108.json").read_bytes()


def at(y: int, m: int, d: int, h: int = 0, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=timezone.utc)


class OfficialCpiPreviousPreflightTests(unittest.TestCase):
    def check_no_trade(self, result: dict) -> None:
        for key in ("previous_snapshot_for_model", "nowcast_estimate", "probabilities",
                    "pair_bias", "next_oct2026_cpi_mom_consensus",
                    "next_oct2026_cpi_mom_actual"):
            self.assertIsNone(result[key], key)
        for key in ("can_feed_live_radar", "worker_enabled", "automatic_execution"):
            self.assertFalse(result[key], key)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["new_cost_brl"], 0)

    def test_casebook_sha_is_pinned_to_exact_transcription(self):
        self.assertEqual(sha256(RECEIPT).hexdigest(), CASEBOOK_SHA256)

    def test_two_bls_releases_are_documentary_only_not_pit_snapshots(self):
        out = inspect(RECEIPT, as_of_utc=at(2026, 11, 9))
        self.assertEqual(out["state"], "LAB_DOCUMENTARY_PREVIOUS_AVAILABLE_NOT_PIT_ATTESTED")
        self.assertEqual(out["prior_cpi_mom_sa_percent_documentary"], 0.6)
        self.assertEqual(out["earlier_cpi_mom_sa_percent_documentary"], 0.4)
        self.assertEqual(out["next_release_scheduled_utc"], "2026-11-10T13:30:00+00:00")
        self.assertEqual(out["reason"], "WAIT_PIT_PREVIOUS_AND_EVENT_CONSENSUS")
        self.assertFalse(out["next_oct2026_cpi_yoy_publishable"])
        self.check_no_trade(out)

    def test_same_source_cannot_backfill_before_research_available(self):
        out = inspect(RECEIPT, as_of_utc=at(2026, 11, 8, 23, 59))
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["reason"], "NO_RESEARCH_BACKFILL_BEFORE_NOV9_UTC")
        self.assertIsNone(out["prior_cpi_mom_sa_percent_documentary"])
        self.check_no_trade(out)

    def test_release_clock_passed_does_not_invent_new_actual(self):
        out = inspect(RECEIPT, as_of_utc=at(2026, 11, 10, 13, 30))
        self.assertEqual(out["reason"], "WAIT_OFFICIAL_OCT2026_CPI_MOM_ACTUAL_AND_ORIGINALS")
        self.check_no_trade(out)

    def test_timezone_equivalence(self):
        local = datetime(2026, 11, 8, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(inspect(RECEIPT, as_of_utc=local),
                         inspect(RECEIPT, as_of_utc=at(2026, 11, 9)))

    def test_naive_and_invalid_clocks_fail_closed(self):
        for invalid in (None, "2026-11-09", datetime(2026, 11, 9)):
            out = inspect(RECEIPT, as_of_utc=invalid)
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.check_no_trade(out)

    def test_tampering_with_previous_or_source_fails_closed(self):
        for bad in (None, "not bytes", RECEIPT + b" ",
                    RECEIPT.replace(b'"0.6"', b'"0.9"'),
                    RECEIPT.replace(b'"original_sha256": null',
                                    b'"original_sha256": "' + b'a'*64 + b'"')):
            out = inspect(bad, as_of_utc=at(2026, 11, 9))
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.check_no_trade(out)


if __name__ == "__main__":
    unittest.main()
