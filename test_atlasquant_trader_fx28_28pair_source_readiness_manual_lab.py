"""Synthetic source inventories only; no bank, MT5, network or account access."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import unittest
from contextlib import redirect_stdout

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    SCHEMA as ARCHIVE_SCHEMA,
)
from atlasquant_trader_fx28_five_bank_capture_once_lab import (
    SCHEMA as CAPTURE_SCHEMA,
)
from atlasquant_trader_fx28_policy_why_wait_matrix_lab import (
    explain_fx28_policy_wait_lab as explain,
)
from atlasquant_trader_fx28_28pair_source_readiness_manual_lab import (
    SCHEMA, inspect_28pair_source_readiness_once_lab as inspect, main,
)

NOW = datetime(2026, 11, 13, 16, 5, tzinfo=timezone.utc)


def archive_snapshot(checked=(), rejected=None):
    good = set(checked)
    reject = dict(rejected or {})
    missing = set(CURRENCIES) - good - set(reject)
    coverage=[]
    two=0
    for pair in OFFICIAL_PAIRS:
        base,quote=split_pair(pair)
        both=base in good and quote in good
        two+=int(both)
        coverage.append({
            "pair":pair,"base_policy_original_locally_checked":base in good,
            "quote_policy_original_locally_checked":quote in good,
            "both_policy_sources_locally_checked":both,
            "cpi_both_currencies_authenticated":False,
            "fx_direction_admissible":False,
        })
    return {
        "schema":ARCHIVE_SCHEMA,
        "state":("LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO"
                 if len(good)==8 else
                 "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO"),
        "currencies_locally_checked":sorted(good),
        "currencies_missing":sorted(missing),
        "currencies_rejected":reject,
        "currencies_with_local_original_bytes_validated":len(good),
        "pairs_with_both_policy_originals_locally_checked":two,
        "pairs_lacking_at_least_one_policy_original":28-two,
        "pair_policy_source_coverage":coverage,
        "operational_bias":"AGUARDAR","trade_authorized":False,
        "publishable":False,"directional_bias":None,
        "calibrated_probability":None,
        "source_current_issuer_identity_independently_verified":False,
        "historical_point_in_time_vintage_verified":False,
        "cpi_for_all_eight_currencies_authenticated":False,
        "differing_policy_instruments_harmonized":False,
    }


def capture_packet(*, attempts=5):
    return {
        "schema": CAPTURE_SCHEMA,
        "state":"LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO",
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,
        "publishable":False,
        "https_gets_attempted_or_started":attempts,
        "currency_results":{
            x:"FETCH_VALIDATE_OR_SAVE_FAILED"
            for x in ("GBP","JPY","CHF","AUD","NZD")},
    }


class Fx28ReadinessCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archive=Mock(return_value=archive_snapshot(("USD","EUR","CAD")))
        self.capture=Mock(return_value=capture_packet())
        self.explain=Mock(side_effect=lambda *,archive_report:explain(
            archive_report=archive_report))

    def run_it(self, *, mode="audit", root=None, clock=lambda: NOW):
        return inspect(mode=mode,
                       local_appdata=self.tmp.name if root is None else root,
                       decision_clock=clock,
                       capture=self.capture,archive=self.archive,
                       explain=self.explain)

    def safe(self, r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for flag in ("trade_authorized","publishable","live_alert_allowed",
                     "worker_enabled","scheduler_enabled",
                     "first_seen_pit_authenticated",
                     "central_bank_issuer_independently_authenticated",
                     "bilateral_cpi_yoy_authenticated","broker_m15_verified",
                     "pre_event_forecasts_independently_witnessed",
                     "forecast_or_accuracy_validated"):
            self.assertFalse(r[flag],flag)
        self.assertTrue(r["source_coverage_is_not_currency_strength"])
        self.assertEqual(r["paid_data_requests"],0)
        self.assertEqual(r["new_cost_brl"],0)
        self.assertLessEqual(r["manual_capture_reported_http_attempts"],5)
        for row in r["per_pair"]:
            self.assertEqual(row["bias"],"AGUARDAR")
            self.assertFalse(row["trade_authorized"])
            self.assertNotIn("probability",row)

    def blocked(self, **kwargs):
        r=self.run_it(**kwargs)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_28PAIR_READINESS_BLOCKED")
        self.assertEqual(r["per_pair"],[])
        return r

    def test_01_no_flag_means_zero_replay_or_capture(self):
        for bad in (None,"",True,1,"go","capture","--audit"):
            with self.subTest(mode=bad):
                self.blocked(mode=bad)
        self.capture.assert_not_called()
        self.archive.assert_not_called()

    def test_02_readonly_audit_28_explanations_three_of_eight(self):
        r=self.run_it()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO")
        self.assertEqual(r["pairs_explained"],28)
        self.assertEqual(r["local_policy_sources_checked_codes"],
                         ["CAD","EUR","USD"])
        self.assertEqual(r["pairs_with_two_policy_sources_locally_checked"],3)
        self.assertEqual(r["policy_sources_missing_or_rejected_codes"],
                         ["AUD","CHF","GBP","JPY","NZD"])
        self.assertEqual([x["pair"] for x in r["per_pair"]],list(OFFICIAL_PAIRS))
        self.assertEqual(r["manual_capture_reported_http_attempts"],0)
        self.capture.assert_not_called()
        self.archive.assert_called_once()

    def test_03_audit_no_bank_documents_still_28_clear_reasons(self):
        self.archive.return_value=archive_snapshot()
        r=self.run_it()
        self.safe(r)
        self.assertEqual(r["pairs_explained"],28)
        self.assertEqual(r["local_policy_sources_checked_count"],0)
        self.assertTrue(all(
            x["why_wait_code"]=="POLICY_ORIGINAL_MISSING"
            for x in r["per_pair"]))

    def test_04_all_eight_local_source_claims_still_no_direction(self):
        self.archive.return_value=archive_snapshot(CURRENCIES)
        r=self.run_it()
        self.safe(r)
        self.assertEqual(r["pairs_with_two_policy_sources_locally_checked"],28)
        self.assertEqual(r["policy_sources_missing_or_rejected_codes"],[])
        self.assertEqual(r["suggested_next_collection_by_documentary_coverage"],[])
        self.assertTrue(all("CPI" in x["why_wait_code"] for x in r["per_pair"]))

    def test_05_capture_missing_opt_in_calls_existing_collector_once(self):
        r=self.run_it(mode="capture_missing")
        self.safe(r)
        self.capture.assert_called_once()
        args=self.capture.call_args.kwargs
        self.assertIs(args["capture_missing"],True)
        self.assertEqual(args["local_appdata"],self.tmp.name)
        self.assertEqual(r["mode"],"capture_missing")
        self.assertEqual(r["manual_capture_reported_http_attempts"],5)
        self.assertEqual(set(r["manual_capture_results"]),
                         {"GBP","JPY","CHF","AUD","NZD"})
        self.archive.assert_called_once()

    def test_06_partial_capture_does_not_become_signal_or_proof(self):
        self.archive.return_value=archive_snapshot(("USD","EUR","CAD","GBP"),
                                                    {"AUD":"HTTP_403"})
        r=self.run_it(mode="capture_missing")
        self.safe(r)
        self.assertEqual(r["pairs_explained"],28)
        self.assertIn("AUD",r["policy_sources_missing_or_rejected_codes"])
        aud=next(x for x in r["per_pair"] if x["pair"]=="AUD/USD")
        self.assertEqual(aud["why_wait_code"],"POLICY_ORIGINAL_REJECTED")

    def test_07_if_real_folder_missing_do_not_invent_28_missing(self):
        self.archive.return_value={
            "state":"LAB_FX28_POLICY_ARCHIVE_REPLAY_BLOCKED",
            "reason":"LOCAL_ISSUER_ARCHIVE_FOLDER_MISSING"}
        r=self.blocked()
        self.assertEqual(r["reason"],"POLICY_ARCHIVE_ABSENT_OR_REJECTED")
        self.capture.assert_not_called()
        self.explain.assert_not_called()

    def test_08_bad_archive_shape_blocks_without_fake_roster(self):
        for result in (None,42,{},{"state":"WRONG"}):
            with self.subTest(report=result):
                self.archive.return_value=result
                r=self.blocked()
                self.assertEqual(r["reason"],
                                 "POLICY_ARCHIVE_ABSENT_OR_REJECTED")

    def test_09_invalid_path_zero_collector_calls(self):
        for bad in ("",".","relative",True,42):
            with self.subTest(path=bad):
                self.blocked(mode="capture_missing",root=bad)
        self.capture.assert_not_called()
        self.archive.assert_not_called()

    def test_10_symlink_prevents_read_and_network(self):
        base=Path(self.tmp.name)
        destination=base/"actual";destination.mkdir()
        (base/"AtlasQuant").symlink_to(destination,target_is_directory=True)
        r=self.blocked(mode="capture_missing")
        self.assertEqual(r["reason"],"UNSAFE_LOCAL_APPDATA_OR_CLOCK")
        self.archive.assert_not_called()
        self.capture.assert_not_called()

    def test_11_bad_clock_and_backward_clock_block(self):
        for moment in (None,NOW.replace(tzinfo=None),NOW.replace(microsecond=1)):
            with self.subTest(time=moment):
                r=self.blocked(mode="capture_missing",clock=lambda:moment)
                self.assertEqual(r["reason"],"UNSAFE_LOCAL_APPDATA_OR_CLOCK")
        self.capture.assert_not_called()
        self.archive.assert_not_called()
        seq=iter((NOW,NOW-timedelta(minutes=1)))
        r=self.blocked(clock=lambda:next(seq))
        self.assertEqual(r["reason"],"POST_ACTION_CLOCK_REWOUND")

    def test_12_capture_exception_and_invalid_packet_block(self):
        self.capture.side_effect=OSError("synthetic 403")
        r=self.blocked(mode="capture_missing")
        self.assertEqual(r["reason"],"MANUAL_CAPTURE_THROWN_EXCEPTION")
        self.archive.assert_not_called()
        self.capture.side_effect=None
        for bad in (None,{},{"schema":CAPTURE_SCHEMA}):
            with self.subTest(packet=bad):
                self.capture.return_value=bad
                r=self.blocked(mode="capture_missing")
                self.assertEqual(r["reason"],
                                 "MANUAL_CAPTURE_REJECTED_OR_INCOHERENT")

    def test_13_suspicious_http_count_or_currency_status_rejected(self):
        for mode in ("negative","six","no_status","extra"):
            with self.subTest(mode=mode):
                p=capture_packet()
                if mode=="negative":
                    p["https_gets_attempted_or_started"]=-1
                elif mode=="six":
                    p["https_gets_attempted_or_started"]=6
                elif mode=="no_status":
                    p["currency_results"]={}
                else:
                    p["currency_results"]["USD"]="DID_NOT_EXPECT"
                self.capture.return_value=p
                r=self.blocked(mode="capture_missing")
                self.assertEqual(r["reason"],
                                 "MANUAL_CAPTURE_COUNTS_OR_SOURCE_STATUS_INVALID")
        self.archive.assert_not_called()

    def test_14_bad_explainer_claiming_direction_or_trade_blocked(self):
        honest=explain(archive_report=archive_snapshot(("USD","EUR")))
        for key,value in (("state","LIVE_GO"),
                          ("operational_bias","COMPRAR"),
                          ("trade_authorized",True),
                          ("publishable",True),
                          ("pairs_admitted_for_direction",28)):
            with self.subTest(key=key):
                bad=deepcopy(honest)
                bad[key]=value
                self.explain.side_effect=None
                self.explain.return_value=bad
                r=self.blocked()
                self.assertEqual(r["reason"],
                                 "FX28_EXPLANATION_NOT_ADMISSIBLE")

    def test_15_one_rogue_pair_from_explainer_blocks_all_28(self):
        honest=explain(archive_report=archive_snapshot(("EUR","USD")))
        for field,bad in (("pair","XAU/USD"),("trade_authorized",True),
                          ("operational_bias","COMPRA"),
                          ("fx_direction_admissible",True),
                          ("independently_witnessed_directional_bias","UP")):
            with self.subTest(field=field):
                new=deepcopy(honest)
                new["per_pair"][4][field]=bad
                self.explain.side_effect=None
                self.explain.return_value=new
                r=self.blocked()
                self.assertEqual(r["reason"],
                                 "FX28_28_PAIR_ROSTER_OR_NO_GO_CONTRACT_INVALID")

    def test_16_immutable_input_report_and_no_private_paths_in_output(self):
        report=archive_snapshot(("USD","EUR","CAD"))
        initial=deepcopy(report)
        self.archive.return_value=report
        r=self.run_it()
        self.safe(r)
        self.assertEqual(report,initial)
        payload=str(r)
        self.assertNotIn(self.tmp.name,payload)
        self.assertNotIn("first_seen_verified=true",payload)

    def test_17_command_without_option_does_not_execute_any_audit(self):
        out=io.StringIO()
        with patch("atlasquant_trader_fx28_28pair_source_readiness_manual_lab.inspect_28pair_source_readiness_once_lab") as run_mock:
            run_mock.return_value={
                "state":"LAB_FX28_28PAIR_READINESS_BLOCKED",
                "operational_bias":"AGUARDAR",
            }
            with redirect_stdout(out):
                code=main([])
            self.assertEqual(code,2)
            self.assertIsNone(run_mock.call_args.kwargs["mode"])

    def test_18_manual_audit_flag_never_becomes_capture_flag(self):
        out=io.StringIO()
        with patch("atlasquant_trader_fx28_28pair_source_readiness_manual_lab.inspect_28pair_source_readiness_once_lab") as run_mock:
            run_mock.return_value={
                "state":"LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO",
                "operational_bias":"AGUARDAR",
            }
            with redirect_stdout(out):
                code=main(["--audit"])
            self.assertEqual(code,0)
            self.assertEqual(run_mock.call_args.kwargs["mode"],"audit")
        with patch("atlasquant_trader_fx28_28pair_source_readiness_manual_lab.inspect_28pair_source_readiness_once_lab") as run_mock:
            run_mock.return_value={
                "state":"LAB_FX28_28PAIR_READINESS_BLOCKED",
                "operational_bias":"AGUARDAR",
            }
            with redirect_stdout(out):
                code=main(["--capture-missing"])
            self.assertEqual(code,2)
            self.assertEqual(run_mock.call_args.kwargs["mode"],"capture_missing")

    def test_19_capture_and_audit_flags_mutually_exclusive(self):
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as e:
                main(["--audit","--capture-missing"])
        self.assertNotEqual(e.exception.code,0)


if __name__=="__main__":
    unittest.main()
