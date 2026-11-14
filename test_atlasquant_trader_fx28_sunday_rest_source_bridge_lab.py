"""Offline Sunday pre-window contract: REST comment metadata is not forecast.

Uses real parser, real 672 ledger and, for one test, real local source
panel reading SYNTHETIC temporary-dir files. No HTTP/AM12/MT5/orders.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
import unittest

from atlasquant_trader_fx28_github_rest_comment_inventory_lab import (
    inspect_github_rest_comment_pages_lab as inventory,
)
from atlasquant_trader_fx28_single_readiness_panel_lab import (
    inspect_fx28_single_readiness_panel_lab as panel,
)
from atlasquant_trader_fx28_sunday_rest_source_bridge_lab import (
    FIRST_PRECOMMIT_ALLOWED_UTC,
    inspect_sunday_fx28_cross_source_preflight_lab as check,
)
from test_atlasquant_trader_fx28_github_rest_comment_inventory_lab import (
    fixture_comment, pages, witness,
)
from test_atlasquant_trader_fx28_sunday_real_reader_preflight_lab import (
    synth_folder,
)

UTC=timezone.utc
PREFLIGHT=datetime(2026,11,15,10,0,tzinfo=UTC)
OPEN=datetime(2026,11,15,22,0,tzinfo=UTC)
PREVIEW=datetime(2026,11,15,9,59,59,tzinfo=UTC)
OLD_COMMENT="2026-11-14T13:00:00Z"


def ordinary(now, *, created=OLD_COMMENT):
    return inventory(raw_pages=pages(fixture_comment(
        body="Checkpoint narrative only; no precommit.",created=created,updated=created)),
        observed_at_utc=now)


def witness_report(now, horizons=("D1",), *, created="2026-11-15T10:00:00Z"):
    records=[]
    for i,horizon in enumerate(horizons):
        records.append(fixture_comment(
            comment_id=5001+i, body=witness(horizon=horizon),
            created=created, updated=created))
    return inventory(raw_pages=pages(*records),observed_at_utc=now)


class SundayRestLedgerSourceBridgeTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for key in ("trade_authorized","publishable","live_alert_allowed",
                    "scheduler_enabled","worker_enabled",
                    "rest_candidate_roster_bytes_authenticated",
                    "rest_snapshot_is_not_external_independent_precommit_proof",
                    "local_am12_connection_and_originals_independently_verified",
                    "all_56_first_window_forecasts_authenticated",
                    "pre_event_risk_or_source_coverage_sufficient_for_direction",
                    "macro_pit_independently_verified",
                    "broker_price_point_in_time_verified"):
            if key=="rest_snapshot_is_not_external_independent_precommit_proof":
                self.assertTrue(r[key],key)
            else:
                self.assertFalse(r[key],key)
        self.assertTrue(r["rest_server_timestamps_are_not_immutable_first_seen"])
        self.assertTrue(r["no_supplied_witness_never_proves_github_absence"])
        self.assertTrue(r["prewindow_absence_is_not_missing_forecast_yet"])
        self.assertTrue(r["coverage_missing_input_never_promoted_to_not_issued"])
        self.assertTrue(r["rest_metadata_never_promoted_to_directional_forecast"])
        for key in ("validated_direction_accuracy","calibrated_fx_probability"):
            self.assertIsNone(r[key])
        self.assertEqual((r["http_requests"],r["file_writes"],r["new_cost_brl"]),
                         (0,0,0))

    def report(self,now=PREFLIGHT,inv=None,local=None):
        if inv is None:
            inv=ordinary(now)
        r=check(inspected_at_utc=now,github_rest_inventory=inv,
                local_document_panel=local)
        self.safe(r)
        return r

    def test_01_exact_sunday_06_clock_first_56_not_yet_due(self):
        self.assertEqual(FIRST_PRECOMMIT_ALLOWED_UTC,PREFLIGHT)
        r=self.report()
        self.assertEqual(
            r["state"],"LAB_SUNDAY_FX28_REST_LEDGER_SOURCE_SEPARATED_NO_GO")
        self.assertEqual(r["first_window_phase"],"PREWINDOW_OPEN_NOT_YET_DUE")
        self.assertEqual(r["first_56_slots_not_yet_due"],56)
        self.assertEqual(r["first_56_slots_due_now"],0)
        self.assertEqual(r["ledger_slots_accounted"],672)
        self.assertEqual(r["ledger_future_no_supplied_witness"],672)
        self.assertEqual(r["ledger_past_no_supplied_witness"],0)
        self.assertEqual(r["rest_exact_headers_observed_claim"],0)
        self.assertEqual(r["rest_first_window_candidate_count_claim"],0)
        self.assertIsNone(r["local_policy_document_count_supplied_claim"])

    def test_02_just_before_06_cannot_call_missing_commitment(self):
        r=self.report(now=PREVIEW)
        self.assertEqual(r["first_window_phase"],"NOT_ELIGIBLE_BEFORE_FIRST_12H")
        self.assertEqual(r["first_56_slots_due_now"],0)
        self.assertEqual(r["ledger_past_no_supplied_witness"],0)

    def test_03_end_of_prewindow_no_witness_is_still_future(self):
        t=OPEN-timedelta(seconds=1)
        r=self.report(now=t)
        self.assertEqual(r["first_window_phase"],"PREWINDOW_OPEN_NOT_YET_DUE")
        self.assertEqual(r["first_56_slots_not_yet_due"],56)
        self.assertEqual(r["ledger_past_no_supplied_witness"],0)

    def test_04_at_18_open_claims_missing_only_in_supplied_ledger(self):
        r=self.report(now=OPEN)
        self.assertEqual(r["first_window_phase"],
                         "OPENED_NO_RETROSPECTIVE_WITNESS")
        self.assertEqual(r["first_56_slots_due_now"],56)
        self.assertEqual(r["ledger_future_no_supplied_witness"],616)
        self.assertEqual(r["ledger_past_no_supplied_witness"],56)
        self.assertFalse(r["all_56_first_window_forecasts_authenticated"])
        self.assertTrue(r["no_supplied_witness_never_proves_github_absence"])

    def test_05_valid_header_only_d1_not_28_real_forecasts(self):
        t=PREFLIGHT+timedelta(minutes=1)
        inv=witness_report(t)
        self.assertEqual(inv["structural_prewindow_metadata_candidates"],1)
        r=self.report(now=t,inv=inv)
        self.assertEqual(r["rest_first_window_candidate_count_claim"],1)
        self.assertEqual(r["rest_first_window_candidate_horizons_claim"],["D1"])
        self.assertEqual(r["ledger_future_no_supplied_witness"],672)
        self.assertFalse(r["all_56_first_window_forecasts_authenticated"])
        self.assertFalse(r["trade_authorized"])

    def test_06_even_two_exact_headers_do_not_authenticate_json_roster(self):
        t=PREFLIGHT+timedelta(minutes=1)
        inv=witness_report(t,horizons=("D1","W1"))
        r=self.report(now=t,inv=inv)
        self.assertEqual(r["rest_first_window_candidate_count_claim"],2)
        self.assertEqual(
            r["rest_first_window_candidate_horizons_claim"],["D1","W1"])
        self.assertFalse(r["rest_candidate_roster_bytes_authenticated"])
        self.assertIsNone(r["calibrated_fx_probability"])

    def test_07_past_open_earlier_server_created_does_not_prove_observed(self):
        inv=witness_report(OPEN,horizons=("D1","W1"))
        self.assertEqual(inv["structural_prewindow_metadata_candidates"],0)
        self.assertEqual(inv["late_or_post_window_observed_candidates"],2)
        r=self.report(now=OPEN,inv=inv)
        self.assertEqual(r["rest_first_window_candidate_count_claim"],0)
        self.assertEqual(r["first_56_slots_due_now"],56)
        self.assertFalse(r["rest_candidate_roster_bytes_authenticated"])

    def test_08_no_github_data_is_UNKNOWN_not_zero_comments(self):
        r=check(inspected_at_utc=PREFLIGHT,github_rest_inventory=None)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_SUNDAY_FX28_REST_NOT_OBSERVED_UNKNOWN_NO_GO")
        self.assertIsNone(r["rest_comment_count_observed_claim"])
        self.assertEqual(r["ledger_slots_accounted"],672)
        self.assertEqual(r["local_documentation_status"],
                         "UNKNOWN_NO_CURRENT_AM12_SOURCE_REPORT")

    def test_09_github_api_failed_or_incomplete_does_not_become_no_witness(self):
        inv=ordinary(PREFLIGHT)
        inv["state"]="LAB_GITHUB_REST_COMMENT_INVENTORY_BLOCKED_NO_GO"
        r=self.report(inv=inv)
        self.assertEqual(r["state"],"LAB_SUNDAY_FX28_CROSS_SOURCE_PREFLIGHT_BLOCKED_NO_GO")
        self.assertEqual(
            r["reason"],"GITHUB_REST_INVENTORY_NOT_A_VALID_BOUNDED_REPORT")

    def test_10_stale_or_future_snapshot_cannot_be_prewindow_evidence(self):
        for delta in (timedelta(minutes=11),timedelta(seconds=-1)):
            with self.subTest(delta=delta):
                inv=ordinary(PREFLIGHT)
                when=PREFLIGHT+delta
                r=check(inspected_at_utc=when,github_rest_inventory=inv)
                self.safe(r)
                self.assertEqual(
                    r["reason"],"GITHUB_REST_REPORT_OBSERVATION_CLOCK_MISSING_OR_STALE")

    def test_11_synthetic_six_source_panel_is_only_supplied_not_actual_am12(self):
        with TemporaryDirectory() as td:
            synth_folder(td)
            local=panel(local_appdata=td,inspected_at_utc=PREFLIGHT)
            r=self.report(local=local)
        self.assertEqual(r["local_policy_document_count_supplied_claim"],6)
        self.assertEqual(r["local_recent_24h_currency_count_supplied_claim"],1)
        self.assertEqual(r["local_recent_24h_pair_count_supplied_claim"],0)
        self.assertEqual(r["local_policy_missing_currencies_supplied_claim"],["CHF","JPY"])
        self.assertEqual(
            r["local_documentation_status"],
            "CALLER_SUPPLIED_LOCAL_PANEL_NOT_AM12_INDEPENDENT_ATTESTATION")
        self.assertFalse(r["local_am12_connection_and_originals_independently_verified"])

    def test_12_missing_local_panel_is_unknown_not_last_known_5_of_8(self):
        r=self.report(local=None)
        self.assertEqual(
            r["local_documentation_status"],
            "UNKNOWN_NO_CURRENT_AM12_SOURCE_REPORT")
        self.assertIsNone(r["local_policy_document_count_supplied_claim"])
        self.assertIsNone(r["local_recent_24h_currency_count_supplied_claim"])

    def test_13_forged_local_panel_more_than_eight_or_calibrated_is_blocked(self):
        with TemporaryDirectory() as td:
            synth_folder(td)
            local=panel(local_appdata=td,inspected_at_utc=PREFLIGHT)
        for field,value in (
            ("issuer_policy_document_count",9),
            ("pairs_with_both_policy_documents",28),
            ("recent_24h_local_receipt_claim_count",8),
            ("model_direction_calibrated",True),
            ("slots_past_no_supplied_witness",56),
        ):
            with self.subTest(field=field):
                altered=dict(local);altered[field]=value
                r=self.report(local=altered)
                self.assertEqual(r["state"],
                    "LAB_SUNDAY_FX28_CROSS_SOURCE_PREFLIGHT_BLOCKED_NO_GO")

    def test_14_incoherent_rest_candidate_counts_fail_closed(self):
        inv=ordinary(PREFLIGHT)
        inv["structural_prewindow_metadata_candidates"]=1
        r=self.report(inv=inv)
        self.assertEqual(r["reason"],
                         "GITHUB_REST_CANDIDATE_COUNTS_OR_SHAPE_INCONSISTENT")

    def test_15_bad_user_clock_blocks_without_work(self):
        for value in (None,"2026-11-15T10:00:00Z",
                      PREFLIGHT.replace(tzinfo=None),
                      PREFLIGHT+timedelta(microseconds=1)):
            with self.subTest(value=value):
                r=check(inspected_at_utc=value,github_rest_inventory=None)
                self.safe(r)
                self.assertEqual(
                    r["state"],"LAB_SUNDAY_FX28_CROSS_SOURCE_PREFLIGHT_BLOCKED_NO_GO")


    def test_16_prewindow_two_axis_forecast_unknown_price_future(self):
        r=self.report()
        self.assertTrue(r["coverage_two_axis_nominal_census_reconciled"])
        self.assertEqual(r["coverage_forecast_unknown_no_authenticated_roster"],672)
        self.assertEqual(r["coverage_price_not_yet_labelable_by_clock"],672)
        self.assertEqual(r["coverage_price_closed_but_without_verified_source"],0)
        self.assertEqual(r["ledger_past_no_supplied_witness"],0)

    def test_17_two_hash_only_rest_headers_not_56_auth_forecasts(self):
        at=PREFLIGHT+timedelta(minutes=1)
        r=self.report(now=at,inv=witness_report(at,horizons=("D1","W1")))
        self.assertEqual(r["rest_first_window_candidate_count_claim"],2)
        self.assertEqual(r["coverage_forecast_unknown_no_authenticated_roster"],672)
        self.assertEqual(r["coverage_price_not_yet_labelable_by_clock"],672)
        self.assertTrue(r["coverage_two_axis_nominal_census_reconciled"])
        self.assertFalse(r["all_56_first_window_forecasts_authenticated"])

    def test_18_open_window_is_due_not_finished_and_not_price_unavailable(self):
        at=OPEN+timedelta(seconds=1)
        r=self.report(now=at)
        self.assertEqual(r["ledger_past_no_supplied_witness"],56)
        self.assertEqual(r["ledger_future_no_supplied_witness"],616)
        self.assertEqual(r["coverage_forecast_unknown_no_authenticated_roster"],672)
        self.assertEqual(r["coverage_price_not_yet_labelable_by_clock"],672)
        self.assertEqual(r["coverage_price_closed_but_without_verified_source"],0)

    def test_19_first_d1_close_without_am12_does_not_infer_28_outcomes(self):
        at=OPEN+timedelta(days=1)
        r=self.report(now=at)
        self.assertEqual(r["coverage_forecast_unknown_no_authenticated_roster"],672)
        self.assertEqual(r["coverage_price_closed_but_without_verified_source"],28)
        self.assertEqual(r["coverage_price_not_yet_labelable_by_clock"],644)
        self.assertEqual(r["ledger_past_no_supplied_witness"],84)
        self.assertFalse(r["broker_price_point_in_time_verified"])

    def test_20_rest_unavailable_still_keeps_clock_only_two_axis_status(self):
        r=check(inspected_at_utc=PREFLIGHT,github_rest_inventory=None)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_SUNDAY_FX28_REST_NOT_OBSERVED_UNKNOWN_NO_GO")
        self.assertTrue(r["coverage_two_axis_nominal_census_reconciled"])
        self.assertEqual(r["coverage_forecast_unknown_no_authenticated_roster"],672)
        self.assertIsNone(r["rest_comment_count_observed_claim"])


if __name__=="__main__":
    unittest.main()
