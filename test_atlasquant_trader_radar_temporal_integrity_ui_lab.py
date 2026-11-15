"""UI integration: never promote caller-supplied FX28 clock evidence to accuracy.

No broker, network, filesystem, Streamlit runtime, or score execution.
All fixtures are documentary and unauthenticated, including a perfectly
shaped fake report: the renderer must still say LAB / NÃO OPERAR.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_trader_radar_compact_ui import (
    PAGES, trader_radar_html, _fx28_temporal_integrity_html,
)

SCHEMA = "ATLASQUANT_FX28_672_TEMPORAL_SCORING_INGRESS_FIREWALL_LAB_V1"
STATE = "LAB_FX28_672_FIRST56_AND_SERVER_CLOCK_P0_SCORING_QUARANTINE_NO_GO"


def supplied_documentary_guard():
    return {
        "schema": SCHEMA,
        "state": STATE,
        "frozen_total_slots":672,
        "first_nominal_window_slots_quarantined":56,
        "first_nominal_window_distinct_m15_prices_missing":28,
        "remaining_original_slots_unevaluated":616,
        "first_window_horizons":{"D1":28,"W1":28},
        "sunday_weekly_history_samples":3,
        "matching_server_offset_weekly_minima":3,
        "sunday_clock_p0_status":"3_OF_3_SERVER_GMT_OFFSET_MATCH_HYPOTHESIS_ONLY",
        "source_price_window_complete":False,
        "scoring_ingress_allowed":False,
        "documentary_perfect_score_claim_can_unlock_ingress":False,
        "source_first_seen_broker_authenticated":False,
        "market_server_utc_mapping_independently_attested":False,
        "pre_event_forecasts_independently_authenticated":False,
        "directional_accuracy_validated":False,
        "validated_accuracy":None,
        "calibrated_probability":None,
        "documentary_score_count_released":0,
        "trade_authorized":False,
        "publishable":False,
        "frozen_campaign_slots_modified":False,
        "operational_bias":"AGUARDAR",
    }


class TraderRadarTemporalIntegrityUiTests(unittest.TestCase):
    def test_01_all_three_pages_default_not_connected_not_cleared(self):
        self.assertEqual(tuple(k for k,_ in PAGES),("home","radar","master"))
        for page in ("home","radar","master"):
            with self.subTest(page=page):
                html=trader_radar_html(selected=page)
                self.assertEqual(html.count('data-fx28-temporal-state='),1)
                self.assertIn('data-fx28-temporal-state="NAO_CONECTADO"',html)
                self.assertIn('data-scoring-allowed="false"',html)
                self.assertIn("Assertividade: N/D",html)
                self.assertIn("NÃO OPERAR",html)
                self.assertNotIn("56 registros D1/W1 iniciais",html)

    def test_02_all_three_pages_show_quarantine_when_structurally_consistent(self):
        for page in ("home","radar","master"):
            html=trader_radar_html(
                selected=page,
                temporal_scoring_report=supplied_documentary_guard())
            with self.subTest(page=page):
                self.assertIn('data-fx28-temporal-state="QUARENTENA_LAB"',html)
                self.assertIn("56 registros D1/W1 iniciais em quarentena",html)
                self.assertIn("28 candles M15 nominais ausentes",html)
                self.assertIn("616 registros restantes ainda não",html)
                self.assertIn("GMT+2/GMT+3",html)
                self.assertIn("sem autenticação da corretora",html)
                self.assertIn("Assertividade: N/D; não operar",html)
                self.assertNotIn("100% de acerto",html)

    def test_03_a_fabricated_672_perfect_score_never_visible(self):
        fake=supplied_documentary_guard()
        fake["validated_accuracy"]=100.0
        fake["documentary_score_count_released"]=672
        html=trader_radar_html(selected="master",temporal_scoring_report=fake)
        self.assertIn('data-fx28-temporal-state="RELATORIO_REJEITADO"',html)
        self.assertNotIn("672 acertos",html)
        self.assertNotIn("100.0",html)
        self.assertIn("Assertividade: N/D",html)

    def test_04_missing_schema_blocks_without_counts(self):
        fake=supplied_documentary_guard()
        fake.pop("schema")
        html=_fx28_temporal_integrity_html(fake)
        self.assertIn('data-fx28-temporal-state="RELATORIO_REJEITADO"',html)
        self.assertNotIn("56 registros",html)

    def test_05_spoofed_state_name_blocks(self):
        fake=supplied_documentary_guard()
        fake["state"]="LIVE_GO_REAL"
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_06_wrong_28_28_split_blocks(self):
        fake=supplied_documentary_guard()
        fake["first_window_horizons"]={"D1":27,"W1":29}
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_07_false_672_total_blocks(self):
        fake=supplied_documentary_guard()
        fake["frozen_total_slots"]=671
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_08_56_616_inconsistency_blocks(self):
        fake=supplied_documentary_guard()
        fake["remaining_original_slots_unevaluated"]=615
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_09_bool_is_not_an_integer_count(self):
        fake=supplied_documentary_guard()
        fake["first_nominal_window_slots_quarantined"]=True
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_10_claim_that_clock_is_independently_attested_blocks(self):
        fake=supplied_documentary_guard()
        fake["market_server_utc_mapping_independently_attested"]=True
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_11_fake_independent_pre_event_forecast_attestation_blocks(self):
        fake=supplied_documentary_guard()
        fake["pre_event_forecasts_independently_authenticated"]=True
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_12_fake_live_trading_permission_blocks(self):
        fake=supplied_documentary_guard()
        fake["trade_authorized"]=True
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_13_fake_publishable_blocks(self):
        fake=supplied_documentary_guard()
        fake["publishable"]=True
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))

    def test_14_malicious_html_not_reflected(self):
        fake=supplied_documentary_guard()
        fake["reason"]="<script>alert('forged')</script>"
        fake["some_price"]="1.9999"
        html=_fx28_temporal_integrity_html(fake)
        self.assertNotIn("<script>",html)
        self.assertNotIn("1.9999",html)

    def test_15_wrong_type_spoof_is_fail_closed(self):
        for bad in ([], "GO", object(), 100.0, True):
            with self.subTest(bad_type=type(bad).__name__):
                html=_fx28_temporal_integrity_html(bad)
                self.assertIn("RELATORIO_REJEITADO",html)

    def test_16_report_true_shape_does_not_override_daily_safety_contract(self):
        html=trader_radar_html(
            selected="radar",temporal_scoring_report=supplied_documentary_guard(),
            daily_data={"state":"LIVE_VALIDATED_FAKE","source":"forged"})
        self.assertIn("Dados diários ainda não conectados",html)
        self.assertIn("QUARENTENA_LAB",html)
        self.assertNotIn("LIVE_VALIDATED_FAKE",html)

    def test_17_missing_sunday_history_must_not_show_3_of_3(self):
        fake=supplied_documentary_guard()
        fake["matching_server_offset_weekly_minima"]=2
        html=_fx28_temporal_integrity_html(fake)
        self.assertIn("RELATORIO_REJEITADO",html)
        self.assertNotIn("GMT+2/GMT+3",html)

    def test_18_missing_nominal_m15_count_blocks(self):
        fake=supplied_documentary_guard()
        fake["first_nominal_window_distinct_m15_prices_missing"]=27
        self.assertIn("RELATORIO_REJEITADO",_fx28_temporal_integrity_html(fake))


if __name__=="__main__":
    unittest.main(verbosity=2)
