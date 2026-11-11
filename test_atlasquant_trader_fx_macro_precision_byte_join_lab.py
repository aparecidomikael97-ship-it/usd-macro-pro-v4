"""Offline synthetic G8 CPI/policy byte custody + real precision module integration.

Fixtures are NOT observations, verified issuer documents or trading outcomes.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx_macro_precision_byte_join_lab import (
    inspect_fx_macro_precision_bytes_lab as inspect,
)
from test_atlasquant_trader_precision_gate_orchestrator_lab import fixture as precision_fixture, NOW
from test_atlasquant_trader_g8_macro_matrix_pit_lab import fixtures as macro_fixtures


def evidence():
    receipts = macro_fixtures()
    bodies = {}
    for currency in CURRENCIES:
        bodies[currency] = {}
        for record in receipts[currency]:
            indicator = record["indicator"]
            raw = f"SYNTHETIC_NOT_ISSUER_DOCUMENT:{currency}:{indicator}:2026-09".encode()
            record["source_sha256"] = sha256(raw).hexdigest()
            bodies[currency][indicator] = raw
    return receipts, bodies


def run(*, packet=None, receipts=None, bodies=None, now=NOW):
    default_receipts, default_bodies = evidence()
    return inspect(
        packet=precision_fixture() if packet is None else packet,
        receipts_by_currency=default_receipts if receipts is None else receipts,
        original_source_bytes_by_currency=default_bodies if bodies is None else bodies,
        inspected_at_utc=now,
    )


class MacroPrecisionCustodyJoinTests(unittest.TestCase):
    def safe(self, x):
        self.assertEqual(x["operational_bias"], "AGUARDAR")
        self.assertFalse(x["trade_authorized"])
        self.assertFalse(x["live_alert_allowed"])
        self.assertFalse(x["publishable"])
        self.assertFalse(x["worker_enabled"])
        self.assertFalse(x["scheduler_enabled"])
        self.assertFalse(x["official_publisher_bytes_authenticated"])
        self.assertFalse(x["source_tls_and_release_time_independently_verified"])
        self.assertFalse(x["economic_values_extracted_and_reconciled_to_body"])
        self.assertFalse(x["economic_measurements_and_policy_instruments_harmonized"])
        self.assertFalse(x["historical_point_in_time_independently_verified"])
        self.assertFalse(x["macroeconomic_direction_established"])
        self.assertIsNone(x["predictive_accuracy_validated"])
        self.assertIsNone(x["calibrated_probability"])
        self.assertEqual((x["http_requests"], x["file_writes"], x["new_cost_brl"]), (0, 0, 0))

    def test_all_synthetic_bytes_match_and_seven_filters_still_never_trade(self):
        x = run()
        self.assertEqual(x["state"], "LAB_BYTES_BOUND_MACRO_PRECISION_RESEARCH_CANDIDATE_UNATTESTED")
        self.assertEqual((x["pair_count"], x["d1_macro_claim_complete_pairs"],
                          x["w1_macro_claim_complete_pairs"]), (28, 28, 28))
        self.assertEqual((x["source_body_hashes_supplied"], x["source_body_hashes_matched_local"]), (16, 16))
        self.assertEqual(x["currencies_locally_byte_bound"], 8)
        self.assertEqual(x["pairs_locally_byte_bound_both_sides"], 28)
        self.assertEqual(len(x["precision_stage_reports"]), 7)
        self.assertTrue(x["precision_stage_reports"]["D1_28FX_DATE_COVERAGE"]["structurally_accepted"])
        self.assertEqual(x["precision_blocking_stages"], [])
        self.assertTrue(x["precision_research_candidate_without_macro"])
        self.assertEqual(x["research_candidate_direction"], "BAIXA")
        self.safe(x)

    def test_incomplete_d1_archive_blocks_research_even_with_all_macro_bytes(self):
        p = precision_fixture()
        subset = tuple(s for s in p.d1_coverage_present_symbols if s != "GBPNZD")
        x = run(packet=replace(p, d1_coverage_present_symbols=subset))
        self.assertEqual(x["currencies_locally_byte_bound"], 8)
        self.assertEqual(x["pairs_locally_byte_bound_both_sides"], 28)
        self.assertIn("D1_28FX_DATE_COVERAGE", x["precision_blocking_stages"])
        self.assertEqual(x["precision_stage_reports"]["D1_28FX_DATE_COVERAGE"]["state"],
                         "LAB_SINGLE_PAIR_D1_MISSING_DATE_QUARANTINE")
        self.assertFalse(x["precision_research_candidate_without_macro"])
        self.assertIsNone(x["research_candidate_direction"])
        self.assertEqual(x["state"], "LAB_MACRO_PRECISION_ABSTAIN")
        self.safe(x)

    def test_no_original_source_files_blocks_every_pair_despite_macro_claims(self):
        _, bodies = evidence()
        for cur in CURRENCIES:
            bodies[cur] = {}
        x = run(bodies=bodies)
        self.assertEqual(x["state"], "LAB_MACRO_PRECISION_ABSTAIN")
        self.assertEqual(x["pairs_locally_byte_bound_both_sides"], 0)
        self.assertEqual(x["currencies_locally_byte_bound"], 0)
        self.assertTrue(x["precision_research_candidate_without_macro"])
        self.assertIsNone(x["research_candidate_direction"])
        self.safe(x)

    def test_one_currency_missing_source_blocks_exactly_its_seven_crosses(self):
        _, bodies = evidence()
        bodies["EUR"].pop("CPI_YOY")
        x = run(bodies=bodies)
        self.assertEqual(x["state"], "LAB_MACRO_PRECISION_ABSTAIN")
        self.assertEqual(x["pairs_locally_byte_bound_both_sides"], 21)
        self.assertEqual(x["currencies_locally_byte_bound"], 7)
        for pair in OFFICIAL_PAIRS:
            self.assertEqual(x["pair_rows"][pair]["state"] == "LAB_PAIR_MACRO_WAIT_EVIDENCE",
                             "EUR" in split_pair(pair))
        self.assertIn("EUR_ORIGINAL_BYTES_MISSING_OR_MISMATCHED", x["pair_rows"]["EUR/USD"]["blocking_reasons"])
        self.safe(x)

    def test_tamper_html_bytes_blocks_seven_crosses_even_if_claimed_metadata_complete(self):
        _, bodies = evidence()
        bodies["USD"]["CPI_YOY"] += b"tampered"
        x = run(bodies=bodies)
        self.assertEqual(x["currency_byte_binding"]["USD"]["reason"], "ORIGINAL_BYTES_HASH_MISMATCH")
        self.assertEqual(x["pairs_locally_byte_bound_both_sides"], 21)
        self.assertIsNone(x["research_candidate_direction"])
        self.safe(x)

    def test_g8_source_byte_does_not_authenticate_fake_issuer_value(self):
        x = run()
        self.assertEqual(x["state"], "LAB_BYTES_BOUND_MACRO_PRECISION_RESEARCH_CANDIDATE_UNATTESTED")
        self.assertFalse(x["economic_values_extracted_and_reconciled_to_body"])
        self.assertFalse(x["official_publisher_bytes_authenticated"])
        self.safe(x)

    def test_eur_cpi_missing_receipt_even_if_other_macro_looks_complete(self):
        rec, body = evidence()
        rec["EUR"] = [r for r in rec["EUR"] if r["indicator"] != "CPI_YOY"]
        body["EUR"].pop("CPI_YOY")
        x = run(receipts=rec,bodies=body)
        self.assertEqual((x["d1_macro_claim_complete_pairs"],x["w1_macro_claim_complete_pairs"]),(21,21))
        self.assertEqual(x["pairs_locally_byte_bound_both_sides"], 21)
        self.assertEqual(x["state"],"LAB_MACRO_PRECISION_ABSTAIN")
        self.safe(x)

    def test_later_usd_release_known_by_daily_but_not_weekly_must_not_leak(self):
        rec, bodies = evidence()
        for row in rec["USD"]:
            if row["indicator"] == "POLICY_RATE":
                row["published_at_utc"] = "2026-11-10T12:00:00Z"
                row["captured_at_utc"] = "2026-11-10T12:05:00Z"
        x=run(receipts=rec,bodies=bodies)
        self.assertEqual(x["d1_macro_claim_complete_pairs"],28)
        self.assertEqual(x["w1_macro_claim_complete_pairs"],21)
        self.assertIn("WEEKLY_CPI_POLICY_METADATA_INCOMPLETE_OR_INVALID",x["pair_rows"]["EUR/USD"]["blocking_reasons"])
        self.assertEqual(x["state"],"LAB_MACRO_PRECISION_ABSTAIN")
        self.safe(x)

    def test_future_publication_blocks_seven_crosses_from_both_cutoffs(self):
        rec,bodies=evidence()
        rec["EUR"][0]["published_at_utc"]="2026-11-11T12:00:01Z"
        rec["EUR"][0]["captured_at_utc"]="2026-11-11T12:00:02Z"
        x=run(receipts=rec,bodies=bodies)
        self.assertEqual((x["d1_macro_claim_complete_pairs"],x["w1_macro_claim_complete_pairs"]),(21,21))
        self.safe(x)

    def test_multi_vintage_not_silently_selected(self):
        rec,bodies=evidence()
        rec["EUR"].append(dict(rec["EUR"][0]))
        x=run(receipts=rec,bodies=bodies)
        self.assertEqual(x["state"],"LAB_MACRO_PRECISION_JOIN_BLOCKED")
        self.assertEqual(x["reason"],"INCOMPLETE_OR_INVALID_G8_ASOF_MACRO_MATRICES")
        self.safe(x)

    def test_cost_veto_prevents_candidate_despite_complete_macro_bytes(self):
        p=precision_fixture()
        bad_quote=replace(p.indicative_quote,ask="1.10200")
        x=run(packet=replace(p,indicative_quote=bad_quote))
        self.assertEqual(x["currencies_locally_byte_bound"],8)
        self.assertIn("M15_PRICE_COST",x["precision_blocking_stages"])
        self.assertEqual(x["state"],"LAB_MACRO_PRECISION_ABSTAIN")
        self.safe(x)

    def test_conflict_matrix_prevents_candidate_with_good_macro_bytes(self):
        p=precision_fixture()
        bad=replace(p.candidate, daily="ALTA", weekly="ALTA")
        x=run(packet=replace(p,candidate=bad))
        self.assertIn("BILATERAL_D1W1",x["precision_blocking_stages"])
        self.assertIsNone(x["research_candidate_direction"])
        self.safe(x)

    def test_pre_release_high_impact_event_veto(self):
        p=precision_fixture()
        x=run(packet=replace(p,high_impact_events=(p.candidate.evaluated_at,)))
        self.assertIn("SELECTIVE_NEWS_OOS",x["precision_blocking_stages"])
        self.safe(x)

    def test_wrong_or_naive_clock_blocks(self):
        p=precision_fixture()
        for v in (NOW.replace(tzinfo=None),NOW-timedelta(days=1)):
            with self.subTest(time=v):
                x=run(packet=p,now=v)
                self.assertEqual(x["state"],"LAB_MACRO_PRECISION_JOIN_BLOCKED")
                self.safe(x)

    def test_missing_source_currency_key_blocks_whole_universe(self):
        rec,bodies=evidence()
        bodies.pop("NZD")
        x=run(receipts=rec,bodies=bodies)
        self.assertEqual(x["reason"],"INVALID_G8_UNIVERSE_OR_DECISION_CUTOFF")
        self.safe(x)

    def test_extra_source_field_block(self):
        rec,bodies=evidence()
        bodies["NZD"]["SECRET_BROKER_TOKEN"]=b"garbage"
        x=run(receipts=rec,bodies=bodies)
        self.assertEqual(x["reason"],"INVALID_SOURCE_BUNDLE_SCHEMA_OR_CURRENCY")
        self.safe(x)

    def test_huge_body_avoids_processing(self):
        rec,bodies=evidence()
        bodies["JPY"]["CPI_YOY"]=b"X"*2_000_001
        x=run(receipts=rec,bodies=bodies)
        self.assertEqual(x["reason"],"INVALID_OR_OVERSIZED_ORIGINAL_BYTES")
        self.safe(x)

    def test_forged_source_string_type_denied(self):
        rec,bodies=evidence()
        bodies["CAD"]["POLICY_RATE"]="not actual bytes"
        x=run(receipts=rec,bodies=bodies)
        self.assertEqual(x["reason"],"INVALID_OR_OVERSIZED_ORIGINAL_BYTES")
        self.safe(x)

    def test_partial_currency_missing_any_indicator_denies_seven_pairs(self):
        rec,bodies=evidence()
        bodies["CHF"]={"CPI_YOY":bodies["CHF"]["CPI_YOY"]}
        x=run(receipts=rec,bodies=bodies)
        self.assertEqual(x["pairs_locally_byte_bound_both_sides"],21)
        self.assertFalse(x["pair_rows"]["USD/CHF"]["both_currency_source_bytes_hash_match"])
        self.safe(x)


if __name__ == "__main__":
    unittest.main()