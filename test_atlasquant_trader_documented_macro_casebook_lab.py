"""Documentary US/EUR macro timeline: no OOS availability from research today."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import unittest

from atlasquant_trader_documented_macro_casebook_lab import (
    SCHEMA, inspect_documented_macro_casebook_lab,
)

CASE = Path(__file__).resolve().parent / "docs" / "continuidade" / "TRADER_US_EUR_DOCUMENTED_MACRO_CASEBOOK_LAB_20261102.json"
EARLIEST = datetime(2026, 11, 3, 0, 1, tzinfo=timezone.utc)


def book():
    return json.loads(CASE.read_text(encoding="utf-8"))


def run(data=None, asof=EARLIEST):
    return inspect_documented_macro_casebook_lab(book() if data is None else data, asof_utc=asof)


def event(data, eid):
    return next(x for x in data["events"] if x["event_id"] == eid)


class DocumentedMacroCasebookLabTests(unittest.TestCase):
    def test_schema_and_documentary_status(self):
        result = run()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "LAB_DOCUMENTED_MACRO_WATCH_NO_PIT_CUSTODY")

    def test_five_events_three_retrospective_two_future(self):
        data = book()
        self.assertEqual(len(data["events"]), 5)
        self.assertEqual(len({x["event_id"] for x in data["events"]}), 5)
        result = run(data)
        self.assertEqual(len(result["past_research"]), 3)
        self.assertEqual(len(result["upcoming_watch"]), 2)
        self.assertEqual(result["expired_calendar"], [])

    def test_known_fed_and_ecb_decisions_not_rate_spread_signal(self):
        data = book()
        fed = event(data, "USD_FOMC_20261028")["facts"]
        ecb = event(data, "EUR_ECB_POLICY_20261029")["facts"]
        self.assertEqual(fed, {"decision": "HOLD", "target_range_lower_pct": 3.75, "target_range_upper_pct": 4.0})
        self.assertEqual(ecb, {"decision": "HOLD", "deposit_facility_pct": 2.5,
                               "main_refinancing_pct": 2.65, "marginal_lending_pct": 2.9})
        self.assertTrue(all(x["macro_direction"] == "UNDETERMINED" for x in run()["past_research"]))

    def test_bls_september_cpi_documentary_actual_not_consensus(self):
        e = event(book(), "USD_CPI_SEP2026_RELEASE_20261014")
        self.assertEqual(e["facts"]["cpi_all_items_yoy_nsa_pct"], 3.7)
        self.assertEqual(e["facts"]["cpi_all_items_mom_sa_pct"], 0.6)
        self.assertIsNone(e["consensus_before_release"])

    def test_future_bls_employment_and_cpi_est_clocks(self):
        items = {x["event_id"]: x for x in run()["upcoming_watch"]}
        self.assertEqual(items["USD_EMPLOYMENT_OCT2026_20261106"]["scheduled_at_utc"], "2026-11-06T13:30:00+00:00")
        self.assertEqual(items["USD_CPI_OCT2026_20261110"]["scheduled_at_utc"], "2026-11-10T13:30:00+00:00")
        self.assertTrue(all(x["event_consensus"] is None and x["actual"] is None for x in items.values()))

    def test_ecb_exact_decision_release_clock_not_fabricated(self):
        e = event(book(), "EUR_ECB_POLICY_20261029")
        self.assertIsNone(e["official_release_at_utc"])
        self.assertIsNone(e["scheduled_at_utc"])
        self.assertIn("NOT release clock", e["timing_note"])

    def test_research_from_november_2_not_backdated_into_october(self):
        self.assertEqual(run(asof=datetime(2026, 10, 27, 0, tzinfo=timezone.utc))["state"],
                         "LAB_MACRO_CASEBOOK_REFUSED")

    def test_research_day_is_not_intraday_capture(self):
        self.assertEqual(run(asof=datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))["state"],
                         "LAB_MACRO_CASEBOOK_REFUSED")

    def test_after_event_calendar_expires_not_actual(self):
        out = run(asof=datetime(2026, 11, 11, 14, tzinfo=timezone.utc))
        self.assertEqual(len(out["upcoming_watch"]), 0)
        self.assertEqual(len(out["expired_calendar"]), 2)
        self.assertTrue(all(x["status"] == "PAST_DUE_NEW_RELEASE_REQUIRED" and x["actual"] is None
                            for x in out["expired_calendar"]))

    def test_consensus_never_fabricated(self):
        out = run()
        self.assertTrue(all(x["event_consensus"] is None for x in out["past_research"] + out["upcoming_watch"]))

    def test_unaudited_market_direction_and_90_percent_not_proven(self):
        out = run()
        self.assertEqual(out["market_impact_direction"], "UNDETERMINED")
        self.assertFalse(out["actual_vs_expected_surprise_computed"])
        self.assertFalse(out["real_oos_authorized"])

    def test_no_live_gate(self):
        for key in ("real_historical_receipt_attested", "real_point_in_time_consensus_attested",
                    "can_feed_live_radar", "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(run()[key], key)

    def test_manifest_claims_of_attestation_rejected(self):
        for key in ("real_historical_capture_attested", "event_specific_consensus_verified",
                    "prices_to_measure_reaction_verified", "source_redistribution_rights_verified"):
            with self.subTest(key=key):
                data = book()
                data[key] = True
                self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_wrong_official_host_rejected(self):
        data = book()
        data["events"][0]["official_url"] = "https://www.bls.gov.example.invalid/archives/cpi.htm"
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_event_currency_source_mismatch_rejected(self):
        data = book()
        data["events"][1]["currency"] = "EUR"
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_extra_retrospective_field_rejected(self):
        data = book()
        data["events"][4]["actual"] = 4.5
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_future_event_cannot_have_facts(self):
        data = book()
        data["events"][4]["facts"] = {"cpi_percent": 5.0}
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_nonnull_consensus_rejected(self):
        data = book()
        data["events"][3]["consensus_before_release"] = 150
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_published_attestation_cannot_be_set_by_hand(self):
        data = book()
        data["events"][0]["published_at_utc_attested"] = True
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_duplicate_event_rejected(self):
        data = book()
        data["events"][3]["event_id"] = data["events"][4]["event_id"]
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_invalid_schedule_time_rejected(self):
        data = book()
        data["events"][3]["scheduled_at_utc"] = "2026-11-06T08:30:00"
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_backdated_research_claim_rejected(self):
        data = book()
        data["usable_from_utc"] = "2026-11-02T00:00:00Z"
        self.assertEqual(run(data)["state"], "LAB_MACRO_CASEBOOK_REFUSED")

    def test_source_document_research_is_not_historical_truth(self):
        for key in ("real_historical_capture_attested", "event_specific_consensus_verified",
                    "prices_to_measure_reaction_verified", "source_redistribution_rights_verified"):
            self.assertIs(book()[key], False)

    def test_naive_asof_rejected(self):
        with self.assertRaises(ValueError):
            run(asof=datetime(2026, 11, 3, 0, 1))


if __name__ == "__main__":
    unittest.main()
