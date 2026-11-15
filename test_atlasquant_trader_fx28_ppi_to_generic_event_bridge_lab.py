"""Offline synthetic integration tests: PPI original-reader -> generic metric.

All fixture source text/prices are SYNTHETIC. We stub only the two locked
pre-event original readers, since CI cannot forge real TD/TE pinned hashes.
BLS table, price CSV+manifest+calendar and all other guards actually run.
This is NOT an AM12 real-data execution or predictive-skill measurement.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import unittest

from atlasquant_trader_fx28_ppi_to_generic_event_bridge_lab import (
    SCHEMA, replay_ppi_originals_to_generic_event_lab as bridge,
)
from test_atlasquant_trader_ppi_one_event_study_join_lab import (
    OneEventStudyJoinTests, NOW,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    td as mock_td, te as mock_te,
    raw as ppi_html, receipt as ppi_receipt,
)


class PpiGenericBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=OneEventStudyJoinTests(
            "test_integrated_synthetic_study_is_one_event_not_seven_trials")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.packet=self.fixture.packet

    def run_bridge(self,*,packet=None,at=NOW,patch_td_te=True,
                   td_override=None,te_override=None):
        with ExitStack() as patches:
            if patch_td_te:
                td=mock_td() if td_override is None else td_override
                te=mock_te() if te_override is None else te_override
                # Mock only test's pinned original TD and TE identity
                # validation. Real BLS parsing and every local FX byte
                # are NOT mocked and must still pass all source joins.
                td["publisher_last_modified_http_claim"]="2026-11-06T14:00:00+00:00"
                for module in (
                    "atlasquant_trader_ppi_one_event_study_join_lab",
                    "atlasquant_trader_fx28_ppi_to_generic_event_bridge_lab",
                ):
                    patches.enter_context(patch(module+
                        ".inspect_ppi_pre_event_snapshot_lab",return_value=td))
                    patches.enter_context(patch(module+
                        ".inspect_te_ppi_snapshot_lab",return_value=te))
            r=bridge(packet=self.packet if packet is None else packet,
                     as_of_utc=at)
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_modified"])
        self.assertFalse(r["original_pre_event_consensus_capture_independently_authenticated"])
        self.assertFalse(r["first_print_publication_time_independently_authenticated"])
        self.assertFalse(r["broker_price_source_independently_authenticated"])
        self.assertFalse(r["ppi_only_isolation_from_other_macro_releases_proven"])
        self.assertEqual(r["pre_event_registered_forecast"],"ABSTAIN")
        self.assertEqual(r["out_of_sample_events_for_calibration"],0)
        self.assertIsNone(r["calibrated_directional_probability"])
        self.assertIsNone(r["validated_fx_accuracy"])
        self.assertEqual((r["http_calls"],r["mt5_calls"],r["file_writes"]),(0,0,0))
        return r

    def success(self,**kwargs):
        r=self.run_bridge(**kwargs)
        self.assertEqual(r["state"],
            "LAB_PPI_TWO_REAL_SOURCE_METRICS_MAPPED_GENERIC_DOCUMENTARY_NO_GO")
        self.assertEqual(r["documentary_metric_count"],2)
        self.assertEqual(r["independent_economic_event_count_documentary"],1)
        self.assertEqual(r["independent_predictive_trial_count"],0)
        self.assertEqual(r["seven_usd_fx_pair_reactions_rechecked"],7)
        self.assertEqual(r["reaction_horizons_rechecked"],["M15","H1","H4"])
        return r

    def blocked(self,**kwargs):
        r=self.run_bridge(**kwargs)
        self.assertEqual(r["state"],
            "LAB_PPI_TO_GENERIC_MACRO_EVENT_BRIDGE_BLOCKED_NO_GO")
        self.assertEqual(r["documentary_metric_count"],0)
        self.assertEqual(r["independent_economic_event_count_documentary"],0)
        self.assertEqual(r["seven_usd_fx_pair_reactions_rechecked"],0)
        return r

    def test_01_two_indicators_remain_one_event_one_packet(self):
        r=self.success()
        self.assertEqual(set(r["metrics"]),{"headline","core"})
        self.assertEqual(r["metrics"]["headline"]["consensus_value_documentary"],"0.4")
        self.assertEqual(r["metrics"]["headline"]["actual_value_documentary"],"0.5")
        self.assertEqual(r["metrics"]["headline"]
                         ["actual_minus_consensus_percentage_points_documentary"],"0.1")
        self.assertEqual(r["metrics"]["core"]
                         ["actual_minus_consensus_percentage_points_documentary"],"-0.1")
        self.assertTrue(r["first_print_and_consensus_source_bytes_replayed_locally"])
        self.assertFalse(r["metrics"]["headline"]["impact_on_usd_calibrated"])
        self.assertIsNone(r["metrics"]["core"]["forecast"])

    def test_02_source_pre_event_original_not_mocked_fails_closed(self):
        self.blocked(patch_td_te=False)

    def test_03_missing_full_packet_fails(self):
        self.blocked(packet=None)

    def test_04_before_h4_window_close_fails(self):
        self.blocked(at=NOW-timedelta(hours=1))

    def test_05_tamper_bls_bytes_keep_old_receipt_fails(self):
        packet=replace(self.packet,bls_html=self.packet.bls_html+b"ONE BYTE")
        self.blocked(packet=packet)

    def test_06_tamper_price_csv_hash_fails(self):
        path=self.fixture.root/"EURUSD_PPI_20261113_M15.csv"
        with path.open("ab") as f:f.write(b"tamper")
        self.blocked()

    def test_07_tamper_capture_manifest_fails(self):
        path=self.fixture.root/"ppi_mt5_capture_manifest.json"
        with path.open("ab") as f:f.write(b"tamper")
        self.blocked()

    def test_08_untrusted_cpi_consensus_substitution_blocks(self):
        fake=mock_td()
        fake["headline_consensus_mom_pct"]="0.6"
        self.blocked(td_override=fake)

    def test_09_wrong_core_consensus_blocks(self):
        fake=mock_te()
        fake["core_consensus_mom_pct"]="0.9"
        self.blocked(te_override=fake)

    def test_10_missing_http_last_modified_metadata_blocks_bridge(self):
        fake=mock_td()
        fake["publisher_last_modified_http_claim"]="not-a-time"
        r=self.blocked(td_override=fake)
        self.assertEqual(r["reason"],"TD_HTTP_LAST_MODIFIED_CLAIM_NOT_AVAILABLE")

    def test_11_source_receipt_date_in_future_no_retroactive_capture(self):
        r=self.blocked(at=NOW-timedelta(days=10))
        self.assertFalse(r["first_print_and_consensus_source_bytes_replayed_locally"])

    def test_12_official_bls_mom_headline_03_is_below_04_consensus(self):
        # Synthetic release HTML reproduces only that numerical relation.
        # It is NOT the real BLS original.
        body=ppi_html(head="0.3",core="0.3")
        packet=replace(self.packet,bls_html=body,
                       bls_capture=ppi_receipt(body))
        r=self.success(packet=packet)
        self.assertEqual(r["metrics"]["headline"]
                         ["actual_minus_consensus_percentage_points_documentary"],"-0.1")
        self.assertEqual(r["metrics"]["core"]
                         ["actual_minus_consensus_percentage_points_documentary"],"0.0")
        self.assertEqual(r["independent_predictive_trial_count"],0)

    def test_13_duplicate_replay_is_pure_and_leaves_all_bytes_unchanged(self):
        before={str(p):p.read_bytes() for p in self.fixture.root.iterdir()
                if p.is_file()}
        first=self.success()
        second=self.success()
        self.assertEqual(first,second)
        for name,payload in before.items():
            self.assertEqual(Path(name).read_bytes(),payload)

    def test_14_naive_as_of_denied(self):
        self.blocked(at=NOW.replace(tzinfo=None))

if __name__=="__main__":
    unittest.main(verbosity=2)
