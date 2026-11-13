"""Synthetic archive snapshots only: no authentic G8 issuer/FX28 signal."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS, CURRENCIES, split_pair
from atlasquant_trader_fx28_policy_local_archive_replay_lab import SCHEMA as ARCHIVE_SCHEMA
from atlasquant_trader_fx28_policy_why_wait_matrix_lab import explain_fx28_policy_wait_lab as explain


def snapshot(good=(), rejected=None):
    good=set(good)
    rejected=dict(rejected or {})
    missing=set(CURRENCIES)-good-set(rejected)
    coverage=[]
    count=0
    for pair in OFFICIAL_PAIRS:
        base,quote=split_pair(pair)
        both=base in good and quote in good
        count+=int(both)
        coverage.append({
            "pair":pair,
            "base_policy_original_locally_checked":base in good,
            "quote_policy_original_locally_checked":quote in good,
            "both_policy_sources_locally_checked":both,
            "cpi_both_currencies_authenticated":False,
            "fx_direction_admissible":False,
        })
    return {
        "schema":ARCHIVE_SCHEMA,
        "state":("LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO"
                 if len(good)==8 else "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO"),
        "currencies_locally_checked":sorted(good),
        "currencies_missing":sorted(missing),
        "currencies_rejected":rejected,
        "currencies_with_local_original_bytes_validated":len(good),
        "pairs_with_both_policy_originals_locally_checked":count,
        "pairs_lacking_at_least_one_policy_original":28-count,
        "pair_policy_source_coverage":coverage,
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,
        "publishable":False,
        "directional_bias":None,
        "calibrated_probability":None,
        "source_current_issuer_identity_independently_verified":False,
        "historical_point_in_time_vintage_verified":False,
        "cpi_for_all_eight_currencies_authenticated":False,
        "differing_policy_instruments_harmonized":False,
    }


class Fx28PolicyWhyWaitTests(unittest.TestCase):
    def safe(self, result):
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertEqual(result["pairs_admitted_for_direction"],0)
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["historical_accuracy_validated"])
        self.assertFalse(result["source_claim_independently_authenticated"])
        self.assertFalse(result["first_seen_macro_vintage_independently_authenticated"])
        self.assertFalse(result["bilateral_cpi_yo_y_verified"])
        self.assertFalse(result["policy_instruments_harmonized"])
        self.assertEqual(result["files_written"],0)
        self.assertEqual(result["http_requests"],0)
        self.assertEqual(result["new_cost_brl"],0)
        for row in result["per_pair"]:
            self.assertEqual(row["operational_bias"],"AGUARDAR")
            self.assertIsNone(row["independently_witnessed_directional_bias"])
            self.assertFalse(row["fx_direction_admissible"])
            self.assertFalse(row["trade_authorized"])

    def block(self, report):
        out=explain(archive_report=report)
        self.safe(out)
        self.assertEqual(out["state"],"LAB_FX28_WHY_WAIT_INPUT_BLOCKED")
        self.assertEqual(out["per_pair"],[])
        return out

    def test_01_no_sources_all_28_marked_missing_without_predictions(self):
        out=explain(archive_report=snapshot())
        self.safe(out)
        self.assertEqual(len(out["per_pair"]),28)
        self.assertEqual(out["pairs_with_two_policy_sources_locally_checked"],0)
        self.assertEqual(out["pairs_with_missing_or_rejected_policy_source"],28)
        self.assertTrue(all(
            row["why_wait_code"]=="POLICY_ORIGINAL_MISSING"
            for row in out["per_pair"]))

    def test_02_three_us_eur_cad_locally_checked_only_three_pairs(self):
        out=explain(archive_report=snapshot(("USD","EUR","CAD")))
        self.safe(out)
        self.assertEqual(len(out["per_pair"]),28)
        self.assertEqual(out["pairs_with_two_policy_sources_locally_checked"],3)
        checked={row["pair"] for row in out["per_pair"]
                 if row["policy_originals_locally_checked"]}
        self.assertEqual(checked,{"EUR/USD","EUR/CAD","USD/CAD"})
        self.assertEqual(out["pairs_with_missing_or_rejected_policy_source"],25)
        self.assertEqual(next(row for row in out["per_pair"]
                              if row["pair"]=="GBP/JPY")["missing_policy_currency_codes"],
                         ["GBP","JPY"])

    def test_03_all_eight_locally_checked_still_28_nontradable(self):
        out=explain(archive_report=snapshot(CURRENCIES))
        self.safe(out)
        self.assertEqual(out["pairs_with_two_policy_sources_locally_checked"],28)
        self.assertEqual(out["pairs_with_missing_or_rejected_policy_source"],0)
        self.assertTrue(all(
            row["why_wait_code"]=="POLICY_ORIGINALS_LOCAL_ONLY_NO_BILATERAL_PIT_CPI"
            for row in out["per_pair"]))

    def test_04_rejected_issuer_reason_retained_with_no_trade(self):
        out=explain(archive_report=snapshot(("USD","EUR"),{"JPY":"SHA_MISMATCH"}))
        self.safe(out)
        row=next(r for r in out["per_pair"] if r["pair"]=="USD/JPY")
        self.assertEqual(row["why_wait_code"],"POLICY_ORIGINAL_REJECTED")
        self.assertEqual(row["rejected_policy_currencies"],{"JPY":"SHA_MISMATCH"})
        self.assertFalse(row["policy_originals_locally_checked"])

    def test_05_tampered_true_direction_source_coverage_rejected(self):
        rep=snapshot(("USD","EUR"))
        row=next(r for r in rep["pair_policy_source_coverage"]
                 if r["pair"]=="EUR/USD")
        row["fx_direction_admissible"]=True
        out=self.block(rep)
        self.assertEqual(out["reason"],"FX28_SOURCE_COVERAGE_CONTRADICTS_CURRENCY_PARTITION")

    def test_06_tampered_pair_identity_and_missing_row_rejected(self):
        for style in ("wrong_pair","duplicate","deleted","extra"):
            with self.subTest(style=style):
                rep=snapshot(("USD","EUR"))
                if style=="wrong_pair":
                    rep["pair_policy_source_coverage"][0]["pair"]="EURZZZ"
                elif style=="duplicate":
                    rep["pair_policy_source_coverage"][1]=deepcopy(
                        rep["pair_policy_source_coverage"][0])
                elif style=="deleted":
                    rep["pair_policy_source_coverage"].pop()
                else:
                    rep["pair_policy_source_coverage"].append(deepcopy(
                        rep["pair_policy_source_coverage"][0]))
                self.block(rep)

    def test_06b_integer_one_or_zero_cannot_masquerade_as_bool(self):
        for flag, value in (
            ("both_policy_sources_locally_checked", 1),
            ("fx_direction_admissible", 0),
            ("cpi_both_currencies_authenticated", 0),
        ):
            with self.subTest(flag=flag):
                rep=snapshot(("EUR","USD"))
                row=next(r for r in rep["pair_policy_source_coverage"]
                         if r["pair"]=="EUR/USD")
                row[flag]=value
                self.assertEqual(
                    self.block(rep)["reason"],
                    "FX28_SOURCE_COVERAGE_CONTRADICTS_CURRENCY_PARTITION")

    def test_07_counters_cannot_be_independently_inflated(self):
        for key in ("currencies_with_local_original_bytes_validated",
                    "pairs_with_both_policy_originals_locally_checked",
                    "pairs_lacking_at_least_one_policy_original"):
            with self.subTest(key=key):
                rep=snapshot(("USD","EUR","CAD"))
                rep[key]+=1
                self.block(rep)

    def test_08_duplicate_or_conflicting_currency_partition_blocks(self):
        for key,value in (
            ("currencies_locally_checked",["USD","USD"]),
            ("currencies_missing",["GBP","GBP"]),
            ("currencies_rejected",{"USD":"wrong"}),
            ("currencies_missing",["NOK"]),
        ):
            with self.subTest(key=key):
                rep=snapshot(("EUR","USD"))
                rep[key]=value
                out=self.block(rep)
                self.assertEqual(out["reason"],"CURRENCY_PARTITION_INCONSISTENT")

    def test_09_8_of_8_label_cannot_be_forced_for_3_sources(self):
        rep=snapshot(("USD","EUR","CAD"))
        rep["state"]="LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO"
        self.assertEqual(self.block(rep)["reason"],"SOURCE_STATE_EIGHT_BANK_CONTRADICTION")

    def test_10_bad_source_report_cannot_promote_production_bias(self):
        for key,value in (
            ("schema","WRONG"),("state","LAB_LIVE_GO"),
            ("operational_bias","COMPRAR"),("trade_authorized",True),
            ("publishable",True),("directional_bias","UP"),
            ("calibrated_probability",0.99),
            ("source_current_issuer_identity_independently_verified",True),
            ("historical_point_in_time_vintage_verified",True),
            ("cpi_for_all_eight_currencies_authenticated",True),
            ("differing_policy_instruments_harmonized",True),
        ):
            with self.subTest(key=key):
                rep=snapshot(("USD","EUR"))
                rep[key]=value
                self.assertEqual(self.block(rep)["reason"],"INVALID_POLICY_ARCHIVE_REPORT")

    def test_11_wrong_shape_rejected_not_interpreted(self):
        for rep in (None,[],True,2,"policy",{"schema":ARCHIVE_SCHEMA}):
            with self.subTest(rep=rep):
                self.block(rep)

    def test_12_invalid_reason_string_rejected(self):
        rep=snapshot(("EUR","USD"),{"JPY":"bad"*101})
        out=self.block(rep)
        self.assertEqual(out["reason"],"CURRENCY_PARTITION_INCONSISTENT")

    def test_13_pair_order_frozen_28_and_no_false_rankings(self):
        out=explain(archive_report=snapshot(("USD","EUR","CAD")))
        self.safe(out)
        self.assertEqual([r["pair"] for r in out["per_pair"]], list(OFFICIAL_PAIRS))
        self.assertFalse(any("probability" in row for row in out["per_pair"]))

    def test_14a_source_priority_three_checked_banks_all_tie_plus_three(self):
        out=explain(archive_report=snapshot(("USD","EUR","CAD")))
        self.safe(out)
        sources=out["next_policy_sources_to_collect"]
        self.assertEqual(len(sources),5)
        self.assertEqual([x["currency"] for x in sources],
                         ["AUD","CHF","GBP","JPY","NZD"])
        self.assertTrue(all(
            x["hypothetical_additional_two_policy_source_pairs"]==3
            and len(x["hypothetical_new_pairs"])==3
            and x["requires_issuer_bytes_and_receipt_validation"]
            and not x["source_first_seen_independently_attested"]
            and not x["direction_or_trade_enabled_by_this_capture"]
            for x in sources
        ))
        self.assertEqual(out["pairs_with_two_policy_sources_locally_checked"],3)
        self.assertEqual(out["pairs_admitted_for_direction"],0)
        self.assertFalse(out["source_priority_is_trade_recommendation"])

    def test_14b_last_missing_source_would_add_seven_pair_documentary_checks(self):
        out=explain(archive_report=snapshot(set(CURRENCIES)-{"JPY"}))
        self.safe(out)
        self.assertEqual(out["pairs_with_two_policy_sources_locally_checked"],21)
        self.assertEqual(out["pairs_with_missing_or_rejected_policy_source"],7)
        self.assertEqual(len(out["next_policy_sources_to_collect"]),1)
        nxt=out["next_policy_sources_to_collect"][0]
        self.assertEqual(nxt["currency"],"JPY")
        self.assertEqual(nxt["hypothetical_additional_two_policy_source_pairs"],7)
        self.assertEqual(len(set(nxt["hypothetical_new_pairs"])),7)
        self.assertFalse(nxt["direction_or_trade_enabled_by_this_capture"])

    def test_14c_zero_source_no_single_bank_adds_pair(self):
        out=explain(archive_report=snapshot())
        self.safe(out)
        self.assertEqual(len(out["next_policy_sources_to_collect"]),8)
        self.assertTrue(all(
            r["hypothetical_additional_two_policy_source_pairs"]==0
            and r["hypothetical_new_pairs"]==[]
            for r in out["next_policy_sources_to_collect"]))
        self.assertTrue(
            out["source_priority_measures_only_hypothetical_pair_documentary_coverage"])

    def test_14d_all_eight_sources_no_collection_needed_still_no_bias(self):
        out=explain(archive_report=snapshot(CURRENCIES))
        self.safe(out)
        self.assertEqual(out["next_policy_sources_to_collect"],[])
        self.assertEqual(out["pairs_with_two_policy_sources_locally_checked"],28)
        self.assertEqual(out["pairs_admitted_for_direction"],0)

    def test_14e_rejected_priority_is_repair_not_buy_signal(self):
        out=explain(archive_report=snapshot(("USD","EUR"),{"JPY":"BAD_SHA"}))
        self.safe(out)
        item=next(x for x in out["next_policy_sources_to_collect"]
                  if x["currency"]=="JPY")
        self.assertEqual(item["current_source_state"],"REJECTED_LOCAL_ARCHIVE")
        self.assertEqual(item["hypothetical_additional_two_policy_source_pairs"],2)
        self.assertFalse(item["direction_or_trade_enabled_by_this_capture"])

    def test_14f_source_priority_on_invalid_report_has_no_misleading_ranking(self):
        rep=snapshot(("USD","EUR"))
        rep["pairs_with_both_policy_originals_locally_checked"]=28
        out=self.block(rep)
        self.assertEqual(out["next_policy_sources_to_collect"],[])
        self.assertEqual(out["pairs_admitted_for_direction"],0)

    def test_14_caller_report_is_never_mutated(self):
        rep=snapshot(("EUR","USD"),{"JPY":"MISSING_BODY"})
        original=deepcopy(rep)
        out=explain(archive_report=rep)
        self.safe(out)
        self.assertEqual(rep,original)


if __name__=="__main__":
    unittest.main()
