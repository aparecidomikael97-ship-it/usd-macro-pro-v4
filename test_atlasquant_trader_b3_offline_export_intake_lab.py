"""Offline B3 CSV intake contract tests; all values are invented fixtures.

No data originated from the B3 market. The 'user export' case is an
UNATTESTED mockup, not proof that an export was made or legally licensed.
"""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone
from atlasquant_trader_b3_offline_export_intake_lab import (
    SCHEMA, DENIED, PENDING, SYNTHETIC, COLUMNS,
    inspect_b3_offline_price_export_lab as inspect,
)

ASOF = datetime(2026,11,5,13,tzinfo=timezone.utc)
HEADER = ",".join(COLUMNS) + "\n"


def csv_sample(*, synthetic=True, instruments=("WIN",)):
    data = [HEADER]
    for ins in instruments:
        symbol = ("SIM_"+ins+"_FAKE_SINGLE_EXPIRY" if synthetic
                  else ins+"Z26")
        kind = ("SIMULATED_REGULAR_TRADE_TICK" if synthetic else
                "PROVIDER_DECLARED_EXECUTED_TRADE_UNVERIFIED")
        before = "2026-11-04T21:24:00Z" if ins=="WIN" else "2026-11-04T21:29:00Z"
        old,new = (160000,162000) if ins=="WIN" else (5500,5540)
        for session,clock,price in (
            ("PRE_20261104",before,old),
            ("POST_20261105","2026-11-05T12:03:00Z",new)):
            data.append(f"{ins},{symbol},{session},{kind},{clock},{price}\n")
    return "".join(data).encode("utf-8")


def manifest(data, *, synthetic=True):
    return {
        "schema": SCHEMA,
        "declared_collection_method":
            "SYNTHETIC_FIXTURE" if synthetic else "USER_MANUAL_EXPORT_UNVERIFIED",
        "declared_origin_label": "SYNTHETIC LOCAL TEST" if synthetic else "USER FILE UNVERIFIED",
        "declared_source_reference": "USER_NOTE:fixture-only-no-authoritative-market-data",
        "declared_rights_status": "NOT_INDEPENDENTLY_REVIEWED",
        "collection_was_automated": False,
        "csv_sha256": hashlib.sha256(data).hexdigest(),
        "fixture_mode": synthetic,
    }


def check(data=None, *, synthetic=True, metadata=None, at=ASOF):
    blob = csv_sample(synthetic=synthetic) if data is None else data
    return inspect(blob, manifest(blob if isinstance(blob, bytes) else b"", synthetic=synthetic) if metadata is None else metadata,
                   evaluated_at=at)


class B3AuthorizedCsvPreparationTests(unittest.TestCase):
    def test_synthetic_win_gap_is_math_only(self):
        r = check()
        self.assertEqual(r["state"], SYNTHETIC)
        self.assertEqual(r["matched_pairs"],1)
        self.assertEqual(r["pair_rows"][0]["arithmetical_candidate_gap_percent"],"1.2500")
        self.assertFalse(r["market_reaction_real_verified"])
        self.assertFalse(r["b3_official_raw_trades_authenticated"])

    def test_synthetic_both_instruments_and_sorted_rows(self):
        csv = csv_sample(instruments=("WDO","WIN"))
        r=check(csv)
        self.assertEqual(r["state"],SYNTHETIC)
        self.assertEqual([x["instrument"] for x in r["pair_rows"]],["WDO","WIN"])
        rows={x["instrument"]:x for x in r["pair_rows"]}
        self.assertEqual(rows["WIN"]["arithmetical_candidate_gap_percent"],"1.2500")
        self.assertEqual(rows["WDO"]["arithmetical_candidate_gap_percent"],"0.7273")

    def test_unverified_manual_file_is_not_authenticated_market_reaction(self):
        data=csv_sample(synthetic=False)
        result=check(data,synthetic=False)
        self.assertEqual(result["state"],PENDING)
        self.assertEqual(result["pair_rows"][0]["declared_contract"],"WINZ26")
        self.assertFalse(result["market_data_access_rights_independently_verified"])
        self.assertFalse(result["pre_row_is_last_actual_trade_proven"])
        self.assertFalse(result["post_row_is_first_actual_trade_proven"])
        self.assertFalse(result["same_contract_claim_independently_confirmed"])
        self.assertFalse(result["real_market_reaction_measured"] if "real_market_reaction_measured" in result else result["market_reaction_real_verified"])

    def test_user_file_can_be_both_winz26_wdoz26_but_still_unverified(self):
        data=csv_sample(synthetic=False,instruments=("WIN","WDO"))
        result=check(data,synthetic=False)
        self.assertEqual(result["state"],PENDING)
        self.assertEqual({x["declared_contract"] for x in result["pair_rows"]},{"WINZ26","WDOZ26"})
        self.assertEqual(result["matched_pairs"],2)
        self.assertFalse(result["b3_official_raw_trades_authenticated"])

    def test_win_distances_to_regular_session_boundaries_are_explicit(self):
        row=check()["pair_rows"][0]
        self.assertEqual(row["pre_sample_seconds_before_scheduled_close"],60)
        self.assertEqual(row["post_sample_seconds_after_candidate_open"],180)
        self.assertEqual(row["calendar_elapsed_seconds_between_samples"],52740)
        self.assertEqual(row["label"],"SAMPLED_POINTS_NOT_VERIFIED_OPENING_GAP")
        self.assertFalse(row["is_verified_opening_gap"])

    def test_wdo_boundary_distances_are_not_win_boundaries(self):
        r=check(csv_sample(instruments=("WDO",)))
        row=r["pair_rows"][0]
        self.assertEqual(row["pre_sample_seconds_before_scheduled_close"],60)
        self.assertEqual(row["post_sample_seconds_after_candidate_open"],180)
        self.assertEqual(row["calendar_elapsed_seconds_between_samples"],52440)
        self.assertFalse(row["is_verified_opening_gap"])

    def test_late_next_session_price_is_not_pretended_to_be_opening_tick(self):
        data=csv_sample().replace(b"2026-11-05T12:03:00Z",
                                  b"2026-11-05T12:30:00Z")
        row=check(data)["pair_rows"][0]
        self.assertEqual(row["post_sample_seconds_after_candidate_open"],1800)
        self.assertFalse(row["is_verified_opening_gap"])
        self.assertFalse(row["verified_first_post_event_trade"])

    def test_early_pre_event_price_does_not_become_last_trade(self):
        data=csv_sample().replace(b"2026-11-04T21:24:00Z",
                                  b"2026-11-04T21:15:00Z")
        row=check(data)["pair_rows"][0]
        self.assertEqual(row["pre_sample_seconds_before_scheduled_close"],600)
        self.assertFalse(row["verified_last_pre_event_trade"])
        self.assertFalse(row["is_verified_opening_gap"])

    def test_declared_trade_at_candidate_next_open_still_is_unverified(self):
        data=csv_sample().replace(b"2026-11-05T12:03:00Z",
                                  b"2026-11-05T12:00:00Z")
        row=check(data)["pair_rows"][0]
        self.assertEqual(row["post_sample_seconds_after_candidate_open"],0)
        self.assertFalse(row["is_verified_opening_gap"])
        self.assertFalse(row["sample_timestamps_are_exchange_attested"])

    def test_manual_source_boundary_seconds_do_not_confer_authenticity(self):
        result=check(csv_sample(synthetic=False),synthetic=False)
        row=result["pair_rows"][0]
        self.assertEqual(row["pre_sample_seconds_before_scheduled_close"],60)
        self.assertEqual(row["post_sample_seconds_after_candidate_open"],180)
        self.assertFalse(row["sample_timestamps_are_exchange_attested"])
        self.assertFalse(row["official_session_exception_calendar_checked"])
        self.assertFalse(row["is_verified_opening_gap"])
        self.assertFalse(result["market_reaction_real_verified"])
        self.assertFalse(result["market_data_access_rights_independently_verified"])

    def test_cannot_treat_future_rows_as_known_on_nov3(self):
        d=csv_sample()
        result=check(d,at=datetime(2026,11,3,19,tzinfo=timezone.utc))
        self.assertEqual(result["state"],DENIED)

    def test_cannot_use_post_session_before_it_begins(self):
        d=csv_sample()
        result=check(d,at=datetime(2026,11,5,11,59,tzinfo=timezone.utc))
        self.assertEqual(result["state"],DENIED)

    def test_pre_tick_outside_win_regular_session(self):
        d=csv_sample().replace(b"2026-11-04T21:24:00Z",b"2026-11-04T21:26:00Z")
        self.assertEqual(check(d)["state"],DENIED)

    def test_pre_tick_at_wdo_regular_close_not_allowed(self):
        d=csv_sample(instruments=("WDO",)).replace(
            b"2026-11-04T21:29:00Z",b"2026-11-04T21:30:00Z")
        self.assertEqual(check(d)["state"],DENIED)

    def test_pre_tick_before_session_start_not_allowed(self):
        d=csv_sample().replace(b"2026-11-04T21:24:00Z",b"2026-11-04T11:59:00Z")
        self.assertEqual(check(d)["state"],DENIED)

    def test_post_tick_before_next_regular_open_not_allowed(self):
        d=csv_sample().replace(b"2026-11-05T12:03:00Z",b"2026-11-05T11:59:59Z")
        self.assertEqual(check(d)["state"],DENIED)

    def test_post_tick_after_regular_close_not_allowed(self):
        d=csv_sample().replace(b"2026-11-05T12:03:00Z",b"2026-11-05T21:30:00Z")
        self.assertEqual(check(d,at=datetime(2026,11,5,22,tzinfo=timezone.utc))["state"],DENIED)

    def test_wrong_future_contract_maturity_cannot_be_swapped(self):
        d=csv_sample(synthetic=False).replace(b"WINZ26",b"WINX26")
        self.assertEqual(check(d,synthetic=False)["state"],DENIED)
        d=csv_sample(synthetic=False).replace(b"WINZ26",b"WINZ27")
        self.assertEqual(check(d,synthetic=False)["state"],DENIED)

    def test_synthetic_fixture_cannot_claim_real_symbol(self):
        d=csv_sample().replace(b"SIM_WIN_FAKE_SINGLE_EXPIRY",b"WINZ26")
        self.assertEqual(check(d)["state"],DENIED)

    def test_manual_claim_cannot_use_simulated_symbol(self):
        d=csv_sample(synthetic=False).replace(b"WINZ26",b"SIM_WIN_FAKE_SINGLE_EXPIRY")
        self.assertEqual(check(d,synthetic=False)["state"],DENIED)

    def test_no_settlement_ohlc_or_adjustment_masked_as_trade(self):
        for quote in (b"B3_SETTLEMENT",b"CANDLE_CLOSE",b"OHLC",b"LAST_INDICATIVE"):
            d=csv_sample(synthetic=False).replace(
                b"PROVIDER_DECLARED_EXECUTED_TRADE_UNVERIFIED",quote)
            self.assertEqual(check(d,synthetic=False)["state"],DENIED)

    def test_no_duplicate_role_can_replace_selected_pre_tick(self):
        d=csv_sample()
        d=d.replace(b"POST_20261105",b"PRE_20261104")
        self.assertEqual(check(d)["state"],DENIED)

    def test_three_rows_cannot_cherry_pick_fastest_or_favorable_quote(self):
        d=csv_sample()
        d+=d.splitlines(keepends=True)[1]
        self.assertEqual(check(d)["state"],DENIED)

    def test_digest_wrong_refused(self):
        d=csv_sample()
        m=manifest(d)
        m["csv_sha256"]="0"*64
        self.assertEqual(check(d,metadata=m)["state"],DENIED)

    def test_digest_recomputed_does_not_authenticate_origin(self):
        d=csv_sample(synthetic=False).replace(b"162000",b"159000")
        m=manifest(d,synthetic=False)
        r=check(d,metadata=m,synthetic=False)
        self.assertEqual(r["state"],PENDING)
        self.assertTrue(r["csv_integrity_matches_claim"])
        self.assertFalse(r["user_provided_origin_independently_verified"])
        self.assertFalse(r["market_reaction_real_verified"])

    def test_collector_cannot_claim_automated_scraping(self):
        d=csv_sample(synthetic=False)
        m=manifest(d,synthetic=False)
        m["collection_was_automated"]=True
        self.assertEqual(check(d,metadata=m,synthetic=False)["state"],DENIED)

    def test_caller_cannot_claim_legal_rights_or_inject_permissions(self):
        d=csv_sample(synthetic=False)
        for key,val in (("declared_rights_status","LICENSE_APPROVED"),
                        ("paid_provider_approved",True),
                        ("market_data_access_rights_independently_verified",True)):
            m=manifest(d,synthetic=False)
            m[key]=val
            self.assertEqual(check(d,metadata=m,synthetic=False)["state"],DENIED)

    def test_collection_method_mismatched_to_fixture_mode_refused(self):
        d=csv_sample()
        m=manifest(d)
        m["declared_collection_method"]="USER_MANUAL_EXPORT_UNVERIFIED"
        self.assertEqual(check(d,metadata=m)["state"],DENIED)
        d=csv_sample(synthetic=False)
        m=manifest(d,synthetic=False)
        m["declared_collection_method"]="SYNTHETIC_FIXTURE"
        self.assertEqual(check(d,metadata=m,synthetic=False)["state"],DENIED)

    def test_manifest_wrong_shape_or_bad_values_refused(self):
        d=csv_sample()
        for m in ({}, [], {"schema":SCHEMA}, {**manifest(d),"fixture_mode":"true"}):
            self.assertEqual(check(d,metadata=m)["state"],DENIED)
        self.assertEqual(inspect(d,None,evaluated_at=ASOF)["state"],DENIED)
        m=manifest(d);m["declared_collection_method"]=[]
        self.assertEqual(check(d,metadata=m)["state"],DENIED)

    def test_reference_source_claim_cannot_be_http_endpoint_or_code(self):
        d=csv_sample()
        for ref in ("https://b3.com.br/crawl","USER_NOTE:\nscript=malicious",
                    "USER_NOTE:"+"x"*200,"b3-feed"):
            m=manifest(d);m["declared_source_reference"]=ref
            self.assertEqual(check(d,metadata=m)["state"],DENIED)

    def test_csv_header_change_wrong_order_or_bom_refused(self):
        d=csv_sample()
        for change in (d.replace(b"contract_id",b"contract"),
                       d.replace(b"session_role",b"session"),
                       b"\xef\xbb\xbf"+d,
                       d.replace(b"instrument,contract_id",b"contract_id,instrument")):
            self.assertEqual(check(change)["state"],DENIED)

    def test_blank_quotes_bad_decimal_formula_and_nan_refused(self):
        d=csv_sample()
        for replacement in (b"0",b"-1",b"NaN",b"1e6",b"=2+2",b"1,2",b"0.00001"):
            bad=d.replace(b",160000\n",b","+replacement+b"\n",1)
            self.assertEqual(check(bad)["state"],DENIED)

    def test_bad_utc_and_naive_future_clock_refused(self):
        d=csv_sample()
        for clock in (b"2026-11-04T21:24:00",b"2026-11-04T18:24:00-03:00",
                      b"2026-11-04T23:59:00Z"):
            bad=d.replace(b"2026-11-04T21:24:00Z",clock)
            self.assertEqual(check(bad)["state"],DENIED)

    def test_invalid_bytes_size_and_missing_rows_refused(self):
        self.assertEqual(inspect(None, manifest(csv_sample()), evaluated_at=ASOF)["state"], DENIED)
        for d in ({},[],b"",b"bad",b"\xff"*100,b"x"*5000,b"\x00"*100):
            self.assertEqual(check(d)["state"],DENIED)

    def test_no_newline_crlf_or_unsafe_control_characters(self):
        for d in (csv_sample().rstrip(b"\n"),
                  csv_sample().replace(b"\n",b"\r\n"),
                  csv_sample()+b"\n",
                  csv_sample().replace(b"WIN,",b"WIN,\t",1)):
            self.assertEqual(check(d)["state"],DENIED)

    def test_no_fake_asof_before_research_start(self):
        self.assertEqual(check(at=datetime(2026,11,2,20,tzinfo=timezone.utc))["state"],DENIED)

    def test_timezone_naive_evaluation_rejected(self):
        with self.assertRaises(ValueError):
            check(at=datetime(2026,11,5,13))

    def test_no_real_data_feed_order_pnl_or_prediction_accuracy(self):
        for r in (check(),check(csv_sample(synthetic=False),synthetic=False)):
            self.assertEqual(r["directional_bias"],"AGUARDAR")
            self.assertIsNone(r["market_price_prediction_accuracy"])
            for flag in ("market_reaction_real_verified","copom_caused_the_gap",
                         "b3_official_raw_trades_authenticated",
                         "market_data_access_rights_independently_verified",
                         "pre_row_is_last_actual_trade_proven",
                         "post_row_is_first_actual_trade_proven",
                         "full_market_tick_history_available",
                         "can_feed_live_radar","trade_authorized",
                         "automated_collection_enabled","b3_boletins_ai_scraping_enabled",
                         "worker_enabled","scheduler_enabled",
                         "render_configuration_changed","paid_provider_approved"):
                self.assertFalse(r[flag],flag)


if __name__=="__main__":
    unittest.main()
