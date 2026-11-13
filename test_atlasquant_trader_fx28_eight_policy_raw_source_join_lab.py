"""Eight-bank policy source JOIN tests; every mock document is SYNTHETIC.

Borrow fixtures from each already-validated issuer-specific test module.
Eight coherent mock raw documents do not imply eight real issuer receipts.
Never touch AM12, HTTP, GitHub comments, MT5 or any financial account.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    inspect_eight_bank_policy_raw_source_join_lab as inspect,
)
from test_atlasquant_trader_us_fed_board_target_range_receipt_lab import (
    html_table as fed_html, receipt as fed_receipt,
)
from test_atlasquant_trader_eur_ecb_dfr_sdmx_receipt_lab import (
    rows as ecb_rows, encode as ecb_encode, receipt as ecb_receipt,
)
from test_atlasquant_trader_gbp_boe_bank_rate_history_receipt_lab import (
    original as boe_html, receipt as boe_receipt,
)
from test_atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    homepage as boj_html, receipt as boj_receipt,
)
from test_atlasquant_trader_chf_snb_current_policy_receipt_lab import (
    html_page as snb_html, receipt as snb_receipt,
)
from test_atlasquant_trader_cad_boc_valet_policy_receipt_lab import (
    payload as boc_json, encode as boc_encode, receipt as boc_receipt,
)
from test_atlasquant_trader_aud_rba_cash_target_receipt_lab import (
    html_page as rba_html, receipt as rba_receipt,
)
from test_atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    html_page as rbnz_html, receipt as rbnz_receipt,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,11,30,tzinfo=UTC)


def synthetic_packets():
    raws={
        "USD":fed_html(),
        "EUR":ecb_encode(ecb_rows()),
        "GBP":boe_html(),
        "JPY":boj_html(),
        "CHF":snb_html(),
        "CAD":boc_encode(boc_json()),
        "AUD":rba_html(),
        "NZD":rbnz_html(),
    }
    receipts={
        "USD":fed_receipt, "EUR":ecb_receipt,
        "GBP":boe_receipt, "JPY":boj_receipt,
        "CHF":snb_receipt, "CAD":boc_receipt,
        "AUD":rba_receipt, "NZD":rbnz_receipt,
    }
    assert set(raws)==set(CURRENCIES)
    return {
        c: {"original_bytes":data, "receipt":receipts[c](data)}
        for c,data in raws.items()
    }


class FX28EightIssuerRawSourceJoinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=synthetic_packets()

    def run_gate(self, packets=None, decision=NOW):
        return inspect(
            source_packets_by_currency=(
                deepcopy(self.sources) if packets is None else packets
            ),
            decision_at_utc=decision,
        )

    def no_go(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["actual_issuer_origin_independently_authenticated"])
        self.assertFalse(r["source_local_http_receipt_is_independent_witness"])
        self.assertFalse(r["policy_first_release_timestamp_authenticated"])
        self.assertFalse(r["historical_asof_vintage_authenticated"])
        self.assertFalse(r["source_bytes_retained_on_am12_independently_verified"])
        self.assertFalse(r["full_bilateral_CPI_YOY_sources_authenticated"])
        self.assertFalse(r["economic_policy_rate_instruments_harmonized"])
        self.assertFalse(r["pre_event_forecast_witnessed"])
        self.assertFalse(r["ny17_m15_pair_outcomes_verified"])
        self.assertFalse(r["pair_horizon_independent_claims"])
        self.assertIsNone(r["calibrated_directional_probability"])
        self.assertIsNone(r["directional_bias"])
        self.assertIsNone(r["historical_accuracy"])
        self.assertEqual(r["http_requests"], 0)
        self.assertEqual(r["files_written"], 0)
        self.assertEqual(r["new_cost_brl"], 0)
        for row in r["pair_policy_source_coverage"]:
            self.assertFalse(row["cpi_both_currencies_authenticated"])
            self.assertFalse(row["fx_direction_admissible"])

    def test_synthetic_eight_8_bytes_pass_structurally_but_no_reality_claim(self):
        r=self.run_gate()
        self.no_go(r)
        self.assertEqual(r["state"],
            "LAB_FX28_EIGHT_POLICY_ORIGINAL_BYTES_LOCAL_ONLY_NO_GO")
        self.assertEqual(r["source_packets_provided"],8)
        self.assertEqual(r["local_source_bytes_reconciled_currency_count"],8)
        self.assertEqual(r["source_parser_contracts_available"],8)
        self.assertEqual(r["locally_checked_currencies"],sorted(CURRENCIES))
        self.assertEqual(r["missing_currencies"],[])
        self.assertEqual(r["rejected_currencies"],{})
        self.assertEqual(r["pairs_with_both_policy_sources_locally_checked_count"],28)
        self.assertEqual(r["pairs_missing_or_rejecting_any_policy_source_count"],0)
        self.assertEqual(len(r["pair_policy_source_coverage"]),28)

    def test_zero_source_packets_does_not_mistake_eight_parsers_for_sources(self):
        r=self.run_gate({})
        self.no_go(r)
        self.assertEqual(r["source_parser_contracts_available"],8)
        self.assertEqual(r["local_source_bytes_reconciled_currency_count"],0)
        self.assertEqual(r["pairs_with_both_policy_sources_locally_checked_count"],0)
        self.assertEqual(r["missing_currencies"],sorted(CURRENCIES))
        self.assertEqual(r["pairs_missing_or_rejecting_any_policy_source_count"],28)

    def test_three_synthetic_source_packets_give_three_policy_only_pairs(self):
        packets={c:deepcopy(self.sources[c]) for c in ("USD","EUR","CAD")}
        r=self.run_gate(packets)
        self.no_go(r)
        self.assertEqual(r["local_source_bytes_reconciled_currency_count"],3)
        self.assertEqual(r["source_packets_provided"],3)
        self.assertEqual(r["pairs_with_both_policy_sources_locally_checked_count"],3)
        self.assertEqual(r["pairs_missing_or_rejecting_any_policy_source_count"],25)
        self.assertEqual(r["missing_currencies"],
                         sorted(set(CURRENCIES)-{"USD","EUR","CAD"}))
        accepted={row["pair"] for row in r["pair_policy_source_coverage"]
                  if row["both_policy_sources_locally_checked"]}
        self.assertEqual(accepted, {"EUR/USD","EUR/CAD","USD/CAD"})

    def test_one_policy_source_never_proves_any_pair(self):
        r=self.run_gate({"USD":deepcopy(self.sources["USD"])})
        self.no_go(r)
        self.assertEqual(r["pairs_with_both_policy_sources_locally_checked_count"],0)

    def test_seven_sources_leave_exactly_seven_pairs_missing_policy(self):
        packets={c:deepcopy(v) for c,v in self.sources.items() if c!="JPY"}
        r=self.run_gate(packets)
        self.no_go(r)
        self.assertEqual(r["local_source_bytes_reconciled_currency_count"],7)
        self.assertEqual(r["pairs_with_both_policy_sources_locally_checked_count"],21)
        self.assertEqual(r["pairs_missing_or_rejecting_any_policy_source_count"],7)
        self.assertEqual(r["missing_currencies"],["JPY"])

    def test_adulterated_original_sha_rejects_only_that_currency(self):
        packets=deepcopy(self.sources)
        packets["CAD"]["original_bytes"] += b" "
        r=self.run_gate(packets)
        self.no_go(r)
        self.assertEqual(r["local_source_bytes_reconciled_currency_count"],7)
        self.assertEqual(r["rejected_currencies"]["CAD"],
                         "ORIGINAL_BODY_SHA256_MISMATCH")
        self.assertEqual(r["pairs_with_both_policy_sources_locally_checked_count"],21)

    def test_each_issuer_original_cannot_be_replaced_with_other_issuer(self):
        for currency in sorted(CURRENCIES):
            with self.subTest(currency=currency):
                packets=deepcopy(self.sources)
                packets[currency]["original_bytes"]=self.sources[
                    "CAD" if currency!="CAD" else "USD"
                ]["original_bytes"]
                r=self.run_gate(packets)
                self.no_go(r)
                self.assertEqual(r["local_source_bytes_reconciled_currency_count"],7)
                self.assertIn(currency,r["rejected_currencies"])

    def test_each_issuer_validated_not_a_generic_self_reported_pass(self):
        for currency in sorted(CURRENCIES):
            with self.subTest(currency=currency):
                packets=deepcopy(self.sources)
                packets[currency]["receipt"]["source_url"]="https://fake-bank.example/"
                r=self.run_gate(packets)
                self.no_go(r)
                self.assertEqual(r["local_source_bytes_reconciled_currency_count"],7)
                self.assertIn(currency,r["rejected_currencies"])

    def test_missing_receipt_or_wrong_packet_shape_rejected(self):
        for packet in (
            {"original_bytes":self.sources["USD"]["original_bytes"]},
            {"original_bytes":self.sources["USD"]["original_bytes"],"receipt":None},
            {"original_bytes":"not bytes","receipt":self.sources["USD"]["receipt"]},
            {"original_bytes":self.sources["USD"]["original_bytes"],
             "receipt":self.sources["USD"]["receipt"],"account":"not allowed"},
            None,
        ):
            with self.subTest(packet=type(packet).__name__):
                r=self.run_gate({"USD":packet})
                self.no_go(r)
                self.assertEqual(r["local_source_bytes_reconciled_currency_count"],0)
                self.assertIn("USD",r["rejected_currencies"])

    def test_unknown_or_outside_g8_currency_blocks_whole_batch(self):
        r=self.run_gate({"ZAR":deepcopy(self.sources["USD"])})
        self.no_go(r)
        self.assertEqual(r["state"],"LAB_FX28_POLICY_RAW_SOURCE_JOIN_BLOCKED")
        self.assertEqual(r["source_packets_provided"],0)

    def test_naive_missing_or_microsecond_clock_blocks(self):
        for clock in (None,NOW.replace(tzinfo=None),NOW.replace(microsecond=1)):
            with self.subTest(clock=clock):
                r=self.run_gate(decision=clock)
                self.no_go(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_POLICY_RAW_SOURCE_JOIN_BLOCKED")

    def test_post_cutoff_receipts_fail_per_issuer_without_backfill(self):
        early=datetime(2026,11,13,10,0,tzinfo=UTC)
        r=self.run_gate(decision=early)
        self.no_go(r)
        self.assertLess(r["local_source_bytes_reconciled_currency_count"],8)
        self.assertGreater(len(r["rejected_currencies"]),0)
        self.assertEqual(r["state"],
                         "LAB_FX28_PARTIAL_OR_REJECTED_POLICY_ORIGINAL_BYTES_NO_GO")

    def test_no_pair_direction_even_if_every_source_local_byte_matches(self):
        r=self.run_gate()
        self.no_go(r)
        self.assertEqual(
            len([row for row in r["pair_policy_source_coverage"]
                 if row["fx_direction_admissible"]]), 0)
        self.assertFalse(r["historical_asof_vintage_authenticated"])
        self.assertFalse(r["full_bilateral_CPI_YOY_sources_authenticated"])

    def test_official_fx28_pair_universe_has_28_nonrepeating_pairs(self):
        self.assertEqual(len(OFFICIAL_PAIRS),28)
        self.assertEqual(len(set(OFFICIAL_PAIRS)),28)
        for pair in OFFICIAL_PAIRS:
            base,quote=split_pair(pair)
            self.assertNotEqual(base,quote)
            self.assertIn(base,CURRENCIES)
            self.assertIn(quote,CURRENCIES)


if __name__=="__main__":
    unittest.main()
