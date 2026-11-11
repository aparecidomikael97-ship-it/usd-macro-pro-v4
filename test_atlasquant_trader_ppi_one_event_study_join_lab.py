"""Synthetic PPI event-study wiring tests, never observed market performance."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch
import csv
import tempfile
import unittest

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    BASELINE_OPEN_UTC, EVENT_UTC, FIELDS, LAST_REQUIRED_CLOSE_UTC, USD_FX,
    ClaimedLocalPriceArchive,
)
from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    SCHEMA as PRICE_MANIFEST_SCHEMA, SOURCE_KIND as PRICE_SOURCE_KIND,
)
from atlasquant_trader_ppi_one_event_study_join_lab import (
    ROOT_EVENT, PpiStudyPacket, inspect_ppi_one_event_study_lab as inspect,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    raw as ppi_html, receipt as ppi_receipt, td, te,
)
from test_atlasquant_trader_us_ppi_pre_event_preview_lab import (
    html as td_html, rec as td_receipt,
)
from test_atlasquant_trader_us_ppi_te_second_consensus_lab import (
    fixture as te_html, cap as te_receipt,
)

NOW = LAST_REQUIRED_CLOSE_UTC + timedelta(minutes=15)


class OneEventStudyJoinTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.rows = {}
        for symbol in USD_FX:
            data = []
            for n in range(17):
                # Deliberately invented prices, never a real PPI price outcome.
                value = Decimal("1") + Decimal(n) * Decimal("0.001")
                if not symbol.startswith("USD"):
                    value = Decimal("1") - Decimal(n) * Decimal("0.001")
                data.append({
                    "time_utc_epoch": str(int(BASELINE_OPEN_UTC.timestamp()) + n * 900),
                    "open": str(value), "high": str(value + Decimal("0.002")),
                    "low": str(value - Decimal("0.002")), "close": str(value),
                    "tick_volume": "40", "spread": "11", "real_volume": "0",
                })
            self.rows[symbol] = data
        self.price_receipt = self.write_prices()
        self.td_body = td_html()
        self.te_body = te_html()
        self.ppi_body = ppi_html()
        self.packet = PpiStudyPacket(
            self.td_body, td_receipt(self.td_body),
            self.te_body, te_receipt(self.te_body),
            self.ppi_body, ppi_receipt(self.ppi_body),
            self.root, self.price_receipt,
        )

    def write_prices(self):
        hashes = {}
        for sym, rows in self.rows.items():
            path = self.root / f"{sym}_PPI_20261113_M15.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            hashes[sym] = sha256(path.read_bytes()).hexdigest()
        # Synthetic, clearly UNATTESTED capture manifest. The real collector
        # creates the corresponding file after checking MT5 symbol metadata.
        manifest = {
            "schema": PRICE_MANIFEST_SCHEMA, "source_kind": PRICE_SOURCE_KIND,
            "captured_at_utc_local_clock_claim": NOW.isoformat(),
            "sha256_by_symbol": hashes, "symbol_count": len(USD_FX),
            "rows_per_symbol": 17,
            "terminal_company_observation_untrusted": "SYNTHETIC_TEST_TERMINAL",
            "active_quote_server_independently_verified": False,
            "symbol_specs_claimed_unattested": {
                sym: {
                    "symbol": sym, "currency_base_claim": sym[:3],
                    "currency_profit_claim": sym[3:],
                    "digits_claim": 3 if sym.endswith("JPY") else 5,
                    "point_quote_units_claim":
                        "0.001" if sym.endswith("JPY") else "0.00001",
                } for sym in USD_FX
            },
            "symbol_specs_observed_locally": True,
            "broker_identity_independently_authenticated": False,
            "candle_utc_independently_authenticated": False,
            "point_in_time_market_data_attested": False,
            "research_only": True, "operational_bias": "AGUARDAR",
            "publishable": False, "trade_authorized": False,
        }
        (self.root / "ppi_mt5_capture_manifest.json").write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        return ClaimedLocalPriceArchive(NOW, hashes)

    @contextmanager
    def isolated_synthetic_pre_event_receipts(self):
        # The real frozen HTML digests CANNOT be synthesized in tests.
        # Mock only these already-unit-tested pre-event reader outputs, while
        # executing the actual BLS Table-1 and seven-CSV guards end to end.
        with (patch("atlasquant_trader_ppi_one_event_study_join_lab.inspect_ppi_pre_event_snapshot_lab",
                    return_value=td()),
              patch("atlasquant_trader_ppi_one_event_study_join_lab.inspect_te_ppi_snapshot_lab",
                    return_value=te())):
            yield

    def run_study(self, packet=None, now=NOW):
        result = inspect(packet=self.packet if packet is None else packet,
                         as_of_utc=now)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["causal_effect_estimated"])
        self.assertFalse(result["original_bls_release_time_independently_verified"])
        self.assertFalse(result["broker_history_and_bid_ask_independently_verified"])
        self.assertEqual(result["independent_directional_trials_verified"], 0)
        self.assertIsNone(result["directional_forecast"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))
        return result

    def test_before_release_waits_without_even_accepting_packet(self):
        result = self.run_study(None, EVENT_UTC - timedelta(seconds=1))
        self.assertEqual(result["state"], "LAB_WAIT_PPI_OFFICIAL_RELEASE")
        self.assertIsNone(result["one_event_study"])

    def test_before_four_hour_window_close_waits(self):
        result = self.run_study(None, LAST_REQUIRED_CLOSE_UTC - timedelta(seconds=1))
        self.assertEqual(result["state"], "LAB_WAIT_FX_FOUR_HOUR_WINDOW")

    def test_at_four_hour_close_still_needs_all_sources(self):
        result = inspect(packet=None, as_of_utc=LAST_REQUIRED_CLOSE_UTC)
        self.assertEqual(result["reason"], "COMPLETE_EIGHT_COMPONENT_PACKET_REQUIRED")
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["one_event_study"])

    def test_unmocked_synthetic_html_cannot_claim_frozen_real_receipts(self):
        result = self.run_study()
        self.assertEqual(result["state"], "LAB_PPI_STUDY_BLOCKED")
        self.assertEqual(result["reason"],
                         "PRE_EVENT_ORIGINAL_BYTES_NOT_MATCHING_FROZEN_SNAPSHOTS")
        self.assertIsNone(result["one_event_study"])

    def test_integrated_synthetic_study_is_one_event_not_seven_trials(self):
        with self.isolated_synthetic_pre_event_receipts():
            result = self.run_study()
        self.assertEqual(result["state"],
                         "LAB_PPI_ONE_EVENT_SEVEN_FX_DOCUMENTARY_NO_GO")
        study = result["one_event_study"]
        self.assertEqual(study["root_event_id"], ROOT_EVENT)
        self.assertEqual((study["economic_event_count_documentary"],
                          study["forex_crosses_observed"]), (1, 7))
        self.assertEqual(study["headline_ppi_surprise_percentage_points"], "0.1")
        self.assertEqual(study["core_ex_food_energy_surprise_percentage_points"], "-0.1")
        self.assertEqual(set(study["fx_usd_normalized_m15_h1_h4_bps"]), set(USD_FX))
        self.assertEqual(set(study["m15_bar_spread_samples_not_intrabar_peak_or_transaction_cost"]), set(USD_FX))
        self.assertTrue(study["broker_execution_costs_not_verified"])
        self.assertTrue(study["intrabar_max_spread_not_measured"])
        self.assertTrue(study["m15_bar_spread_aggregation_not_independently_verified"])
        self.assertEqual(study["m15_bar_spread_samples_not_intrabar_peak_or_transaction_cost"]["EURUSD"]
                         ["baseline_m15_bar_spread_sample_points"], 11)
        self.assertTrue(study["local_mt5_capture_manifest_matched_unattested"])
        self.assertFalse(study["mt5_server_or_broker_independently_authenticated"])
        self.assertEqual(result["economic_events_authenticated"], 0)
        self.assertEqual(set(result["source_stage_states"]), {
            "TD_PRE_EVENT", "TE_PRE_EVENT", "BLS_FIRST_PRINT",
            "SURPRISE_SAME_METRIC", "SEVEN_FX_M15_WINDOWS",
            "SPREAD_POINTS_CONTEXT", "MT5_CAPTURE_MANIFEST"})

    def test_missing_bls_document_blocks_even_with_good_synthetic_previous(self):
        with self.isolated_synthetic_pre_event_receipts():
            result = self.run_study(replace(self.packet, bls_html=None))
        self.assertEqual(result["reason"], "BLS_FIRST_PRINT_UNAVAILABLE_OR_INVALID")
        self.assertIsNone(result["one_event_study"])

    def test_bls_http_403_blocks(self):
        changed = replace(self.packet.bls_capture, status_code=403)
        with self.isolated_synthetic_pre_event_receipts():
            result = self.run_study(replace(self.packet, bls_capture=changed))
        self.assertEqual(result["reason"], "BLS_FIRST_PRINT_UNAVAILABLE_OR_INVALID")

    def test_wrong_core_series_will_not_create_study(self):
        body = ppi_html(swap_core=True)
        with self.isolated_synthetic_pre_event_receipts():
            result = self.run_study(replace(
                self.packet, bls_html=body, bls_capture=ppi_receipt(body)))
        self.assertEqual(result["reason"], "BLS_FIRST_PRINT_UNAVAILABLE_OR_INVALID")

    def test_wrong_bls_digest_never_enters_price_study(self):
        body = ppi_html(head="0.9")
        with self.isolated_synthetic_pre_event_receipts():
            result = self.run_study(replace(self.packet, bls_html=body))
        self.assertEqual(result["reason"], "BLS_FIRST_PRINT_UNAVAILABLE_OR_INVALID")

    def test_missing_fx_pair_blocks_entire_cohort(self):
        (self.root / "USDJPY_PPI_20261113_M15.csv").unlink()
        with self.isolated_synthetic_pre_event_receipts():
            result = self.run_study()
        self.assertEqual(result["reason"], "FULL_SEVEN_PAIR_FX_ARCHIVE_MISSING_OR_FAILED")
        self.assertIsNone(result["one_event_study"])

    def test_tampered_price_bytes_block_entire_cohort(self):
        path = self.root / "EURUSD_PPI_20261113_M15.csv"
        path.write_bytes(path.read_bytes() + b"tampered")
        with self.isolated_synthetic_pre_event_receipts():
            result = self.run_study()
        self.assertEqual(result["reason"], "FULL_SEVEN_PAIR_FX_ARCHIVE_MISSING_OR_FAILED")

    def test_price_capture_before_four_hour_window_blocks(self):
        earlier = replace(self.price_receipt,
                          captured_at_utc=EVENT_UTC + timedelta(hours=2))
        with self.isolated_synthetic_pre_event_receipts():
            result = self.run_study(replace(self.packet, price_archive_receipt=earlier))
        self.assertEqual(result["reason"], "MT5_MANIFEST_AND_PRICE_RECEIPT_DISAGREE")

    def test_missing_capture_manifest_blocks_consolidated_study(self):
        (self.root / "ppi_mt5_capture_manifest.json").unlink()
        with self.isolated_synthetic_pre_event_receipts():
            report = self.run_study()
        self.assertEqual(report["reason"], "MT5_CAPTURE_MANIFEST_MISSING_UNSAFE_OR_INVALID")
        self.assertIsNone(report["one_event_study"])

    def test_replaced_manifest_sha_cannot_pass_even_with_valid_seven_csv_files(self):
        path = self.root / "ppi_mt5_capture_manifest.json"
        manifest = json.loads(path.read_text("utf-8"))
        manifest["sha256_by_symbol"]["EURUSD"] = "f" * 64
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.isolated_synthetic_pre_event_receipts():
            report = self.run_study()
        self.assertEqual(report["reason"], "MT5_MANIFEST_AND_PRICE_RECEIPT_DISAGREE")
        self.assertIsNone(report["one_event_study"])

    def test_wrong_mt5_symbol_specs_refuse_result_before_price_scoring(self):
        path = self.root / "ppi_mt5_capture_manifest.json"
        manifest = json.loads(path.read_text("utf-8"))
        manifest["symbol_specs_claimed_unattested"]["USDJPY"]["currency_profit_claim"] = "EUR"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.isolated_synthetic_pre_event_receipts():
            report = self.run_study()
        self.assertEqual(report["reason"], "MT5_CAPTURE_MANIFEST_MISSING_UNSAFE_OR_INVALID")
        self.assertIsNone(report["one_event_study"])

    def test_false_broker_attestation_cannot_pass_paperwork(self):
        path = self.root / "ppi_mt5_capture_manifest.json"
        manifest = json.loads(path.read_text("utf-8"))
        manifest["active_quote_server_independently_verified"] = True
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.isolated_synthetic_pre_event_receipts():
            report = self.run_study()
        self.assertEqual(report["reason"], "MT5_CAPTURE_MANIFEST_MISSING_UNSAFE_OR_INVALID")

    def test_wrong_manifest_census_or_operational_status_rejected(self):
        path = self.root / "ppi_mt5_capture_manifest.json"
        original = json.loads(path.read_text("utf-8"))
        for field, wrong in (("symbol_count", 6), ("rows_per_symbol", 16),
                             ("research_only", False), ("publishable", True),
                             ("trade_authorized", True),
                             ("point_in_time_market_data_attested", True)):
            with self.subTest(field=field):
                manifest = dict(original)
                manifest[field] = wrong
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.isolated_synthetic_pre_event_receipts():
                    report = self.run_study()
                self.assertEqual(report["reason"], "MT5_CAPTURE_MANIFEST_MISSING_UNSAFE_OR_INVALID")
                self.assertIsNone(report["one_event_study"])

    def test_manifest_capture_clock_before_window_close_rejected(self):
        path = self.root / "ppi_mt5_capture_manifest.json"
        manifest = json.loads(path.read_text("utf-8"))
        manifest["captured_at_utc_local_clock_claim"] = (
            LAST_REQUIRED_CLOSE_UTC - timedelta(minutes=1)).isoformat()
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.isolated_synthetic_pre_event_receipts():
            report = self.run_study()
        self.assertEqual(report["reason"], "MT5_CAPTURE_MANIFEST_MISSING_UNSAFE_OR_INVALID")

    def test_manifest_symlink_is_not_accepted(self):
        path = self.root / "ppi_mt5_capture_manifest.json"
        target = self.root / "raw_manifest.json"
        path.rename(target)
        path.symlink_to(target)
        with self.isolated_synthetic_pre_event_receipts():
            report = self.run_study()
        self.assertEqual(report["reason"], "MT5_CAPTURE_MANIFEST_MISSING_UNSAFE_OR_INVALID")

    def test_future_and_naive_inspection_clocks_block(self):
        for invalid in (None, "2026-11-13T18:00:00Z", NOW.replace(tzinfo=None)):
            with self.subTest(invalid=invalid):
                result = self.run_study(now=invalid)
                self.assertEqual(result["reason"], "INVALID_AS_OF_CLOCK")

    def test_no_false_attribution_of_trading_performance(self):
        with self.isolated_synthetic_pre_event_receipts():
            study = self.run_study()["one_event_study"]
        self.assertTrue(study["price_comparison_is_not_executable_return"])
        self.assertNotIn("winning_pairs", study)
        self.assertNotIn("success_rate", study)
        self.assertNotIn("trade_pnl", study)


if __name__ == "__main__":
    unittest.main(verbosity=2)
