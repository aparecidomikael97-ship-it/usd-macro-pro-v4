"""LAB-only tests: local sealed FX28 archive -> authorized Radar UI path.

Synthetic first-M15 archives are created ONLY in TemporaryDirectory using
the offline fake source. Never connects to MT5 or gets real market prices.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from atlasquant_trader_fx28_temporal_radar_runtime_binding_lab import (
    inspect_fx28_local_temporal_radar_binding_lab as bind,
    SCHEMA,STATE,
)
from atlasquant_trader_fx28_first_m15_atomic_claim_lab import (
    claim_once_lab,WINDOW,CLAIM_NAME,
)
from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import collect_window_lab
from test_atlasquant_trader_fx28_first_m15_no_duplicate_precheck_lab import (
    StrictMock,CLOSED,TERMINAL,
)
from test_atlasquant_trader_fx28_first_m15_archive_census_readonly_lab import (
    OneCandleMock,
)
from atlasquant_reference_ui import reference_html, render_reference_workspace
from atlasquant_trader_radar_compact_ui import _fx28_temporal_integrity_html

UTC=timezone.utc
NOW=datetime(2026,11,15,23,58,tzinfo=UTC)


class TemporalRadarLocalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="AQ_FX28_LAB_RADAR_TEMPORAL_")
        self.addCleanup(self.tmp.cleanup)
        self.local=Path(self.tmp.name)
        self.root=self.local/"AtlasQuant"/"LAB"/"FX28_NY17_M15"
        self.root.mkdir(parents=True)

    def inspect(self, *, clock=NOW, local=None):
        return bind(
            local_appdata=str(self.local) if local is None else local,
            inspected_at_utc=clock)

    def make_archive(self,fake=None):
        fake=StrictMock([]) if fake is None else fake
        claim=claim_once_lab(archive_root=self.root,clock=lambda:CLOSED)
        self.assertTrue(claim["exclusive_claim_created"])
        result=collect_window_lab(fake,window=WINDOW,
            terminal_path=TERMINAL,output_root=self.root,clock=lambda:CLOSED)
        return fake,result

    def test_01_synthetic_sealed_archive_to_sanitized_56_slot_status(self):
        source,archive=self.make_archive()
        self.assertEqual(archive["missing_m15_total"],28)
        n=len(source.calls)
        result=self.inspect()
        self.assertEqual(len(source.calls),n)
        self.assertEqual(result["schema"],SCHEMA)
        self.assertEqual(result["state"],STATE)
        self.assertEqual(result["frozen_total_slots"],672)
        self.assertEqual(result["first_nominal_window_slots_quarantined"],56)
        self.assertEqual(result["first_nominal_window_distinct_m15_prices_missing"],28)
        self.assertEqual(result["remaining_original_slots_unevaluated"],616)
        self.assertEqual(result["first_window_horizons"],{"D1":28,"W1":28})
        self.assertFalse(result["clock_p0_documentary_historical_claims_checked"])
        for key in ("broker_source_independently_authenticated",
                    "github_pre_event_witness_independently_authenticated",
                    "score_allowed","trade_authorized","publishable",
                    "has_local_price_data_exposed"):
            self.assertFalse(result[key])
        self.assertIsNone(result["verified_directional_accuracy"])
        self.assertEqual((result["file_writes"],result["mt5_calls"],
                          result["http_requests"]),(0,0,0))
        self.assertEqual(set(result),{
            "schema","state","frozen_total_slots",
            "first_nominal_window_slots_quarantined",
            "first_nominal_window_distinct_m15_prices_missing",
            "remaining_original_slots_unevaluated","first_window_horizons",
            "clock_p0_documentary_historical_claims_checked",
            "broker_source_independently_authenticated",
            "github_pre_event_witness_independently_authenticated",
            "verified_directional_accuracy","calibrated_probability",
            "score_allowed","trade_authorized","publishable",
            "has_local_price_data_exposed","file_writes","mt5_calls",
            "http_requests","operational_bias",
        })
        self.assertNotIn(str(self.local),str(result))

    def test_02_no_archive_returns_unknown(self):
        self.assertIsNone(self.inspect())

    def test_03_no_local_appdata_returns_unknown(self):
        self.assertIsNone(self.inspect(local=None if False else ""))

    def test_04_relative_directory_denied(self):
        self.assertIsNone(self.inspect(local="AtlasQuant/LAB"))

    def test_05_missing_claim_does_not_automatically_report_28_absent(self):
        self.make_archive()
        (self.root/CLAIM_NAME).unlink()
        self.assertIsNone(self.inspect())

    def test_06_bad_archive_corruption_does_not_report_quarantine(self):
        _,archive=self.make_archive()
        with (Path(archive["archive_dir"])/"EURUSD_M15.csv").open("ab") as f:
            f.write(b"TAMPER")
        self.assertIsNone(self.inspect())

    def test_07_duplicate_local_archive_never_show_clean_receipt(self):
        self.make_archive()
        (self.root/(WINDOW+"_DUPLICATE")).mkdir()
        self.assertIsNone(self.inspect())

    def test_08_28_synthetic_bars_not_the_28_missing_class(self):
        _,archive=self.make_archive(OneCandleMock())
        self.assertEqual(archive["captured_m15_total"],28)
        self.assertIsNone(self.inspect())

    def test_09_one_missing_not_the_56_scope(self):
        _,archive=self.make_archive(OneCandleMock(empty_symbol="EURUSD"))
        self.assertEqual(archive["missing_m15_total"],1)
        self.assertIsNone(self.inspect())

    def test_10_mt5_none_in_fixture_not_m15_empty(self):
        _,archive=self.make_archive(StrictMock(None))
        self.assertEqual(archive["reason"],"MT5_HISTORY_QUERY_FAILED_NONE_EURUSD")
        self.assertIsNone(self.inspect())

    def test_11_naive_and_microsecond_clock_fails_closed(self):
        for clock in (datetime(2026,11,15,23,58),
                      NOW+timedelta(microseconds=1)):
            with self.subTest(clock=str(clock)):
                self.assertIsNone(self.inspect(clock=clock))

    def test_12_before_campaign_window_fails_closed(self):
        self.make_archive()
        self.assertIsNone(self.inspect(
            clock=datetime(2026,11,15,21,0,tzinfo=UTC)))

    def test_13_reference_html_passes_local_quarantine_to_three_tabs(self):
        report=None
        self.make_archive()
        report=self.inspect()
        for tab in ("home","radar","master"):
            markup=reference_html("trader_radar",selected=tab,
                                  temporal_scoring_report=report)
            with self.subTest(tab=tab):
                self.assertIn('data-fx28-temporal-state="QUARENTENA_LOCAL_LAB"',markup)
                self.assertIn("Assertividade: N/D",markup)
                self.assertIn("origem e horário da corretora NÃO autenticados",markup)
                self.assertIn("56 registros D1/W1",markup)
                self.assertNotIn(str(self.local),markup)

    def test_14_reference_html_without_report_is_not_connected(self):
        html=reference_html("trader_radar",selected="home")
        self.assertIn('data-fx28-temporal-state="NAO_CONECTADO"',html)
        self.assertNotIn("56 registros D1/W1",html)

    def test_15_fake_report_rejected_and_cannot_claim_100_percent(self):
        self.make_archive()
        r=self.inspect()
        r["verified_directional_accuracy"]=100.0
        text=_fx28_temporal_integrity_html(r)
        self.assertIn('data-fx28-temporal-state="RELATORIO_REJEITADO"',text)
        self.assertNotIn("100.0",text)

    def test_16_fake_clock_attestation_rejected(self):
        self.make_archive()
        r=self.inspect()
        r["clock_p0_documentary_historical_claims_checked"]=True
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(r))

    def test_17_fake_672_score_unlock_rejected(self):
        self.make_archive()
        r=self.inspect()
        r["score_allowed"]=True
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(r))

    def test_18_runtime_local_radar_does_not_consult_user_session_for_root(self):
        self.make_archive()
        class Session(dict):pass
        class FakeSt:
            def __init__(self):
                self.session_state=Session({
                    "aq_reference_module":("trader_radar","home"),
                    "atlasquant_fx28_archive_root":"/untrusted/overwrite",
                })
            def markdown(self,*args,**kwargs):pass
            def rerun(self):raise AssertionError("Unexpected rerun")
        class Result:
            navigate=None
        html_seen=[]
        def fake_component(**kwargs):
            html_seen.append(kwargs["data"])
            return Result()
        st=FakeSt()
        access={"allowed":True,"role":"ADMIN","display_name":"TEST"}
        # Only the trusted local adapter is allowed to produce the report.
        with (patch("atlasquant_central_hub_ui.assert_area_access"),
              patch("atlasquant_reference_ui._component",
                    return_value=fake_component),
              patch("atlasquant_reference_ui._fx28_runtime_temporal_readonly_report_lab",
                    return_value=self.inspect()) as adapter):
            ok=render_reference_workspace(st,access,"trader_radar")
        self.assertTrue(ok)
        adapter.assert_called_once()
        self.assertEqual(len(html_seen),1)
        self.assertIn('data-fx28-temporal-state="QUARENTENA_LOCAL_LAB"',html_seen[0])
        self.assertNotIn("/untrusted/overwrite",html_seen[0])

    def test_19_other_area_does_not_touch_local_temporal_auditor(self):
        class FakeSt:
            session_state={"aq_reference_module":("central","")}
            def markdown(self,*args,**kwargs):pass
        class Result:
            navigate=None
        def fake_component(**kwargs):return Result()
        st=FakeSt()
        access={"allowed":True,"role":"ADMIN","display_name":"TEST"}
        with (patch("atlasquant_reference_ui._component",
                    return_value=fake_component),
              patch("atlasquant_reference_ui._fx28_runtime_temporal_readonly_report_lab",
                    side_effect=AssertionError("Other area accessed local archive"))):
            # reference_html for central uses a purely presentational layout
            # and does not access the Radar's local frozen archive.
            ok=render_reference_workspace(st,access,"central")
        self.assertTrue(ok)


if __name__=="__main__":
    unittest.main(verbosity=2)
