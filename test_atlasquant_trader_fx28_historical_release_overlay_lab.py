"""Synthetic-only tests: never count archival CHF/JPY as current PIT data.

Actual original issuer HTML/PDF stay on AM12; test fixture names/provenance
are explicitly CLAIMS, not authenticated publisher sources. No network/MT5.
"""
from __future__ import annotations
from copy import deepcopy
import unittest
from atlasquant_fx_universe import CURRENCIES,OFFICIAL_PAIRS
from atlasquant_trader_fx28_policy_local_archive_replay_lab import SCHEMA as CURRENT_SCHEMA
from atlasquant_trader_fx28_historical_release_overlay_lab import (
    SCHEMA,combine_policy_coverage,_RELEASE_PINS
)

CURRENT=("AUD","CAD","EUR","GBP","USD")

def baseline(currencies=CURRENT):
    good=set(currencies)
    return {
        "schema":CURRENT_SCHEMA,
        "state":"LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO",
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,
        "publishable":False,
        "historical_point_in_time_vintage_verified":False,
        "source_current_issuer_identity_independently_verified":False,
        "currencies_locally_checked":sorted(good),
        "currencies_missing":sorted(set(CURRENCIES)-good),
        "currencies_rejected":{},
        "currencies_with_local_original_bytes_validated":len(good),
        "pairs_with_both_policy_originals_locally_checked":len(good)*(len(good)-1)//2,
    }

def documentary_claim(currency):
    pin=_RELEASE_PINS[currency]
    doc={"date":pin["date"],"instrument":pin["instrument"],
        "decision_kind":pin["decision_kind"],pin["rate_key"]:pin["rate"]}
    if currency=="JPY":
        doc.update({"decision_vote_for":8,"decision_vote_against":1,
                    "dissenting_proposal_pct":1.5})
    return {
        "status":"LOCAL_RELEASE_DOCUMENT_CONTENT_AND_SHA_CHECKED_NO_GO",
        "currency":currency,"document":doc,"bytes":pin["bytes"],
        "source_url":pin["url"],"sha256":pin["sha256"],
        "retrieved_after_original_release":True,
        "independent_issuer_origin_attested":False,
        "release_first_seen_authenticated":False,
        "validated_forward_currency_direction":False,
        "trading_authorized":False,
    }

class HistoricalOverlayTests(unittest.TestCase):
    def run_overlay(self,historical=None,current=None):
        o=combine_policy_coverage(
            current_policy_report=baseline() if current is None else current,
            historical_docs=({"CHF":documentary_claim("CHF"),
                              "JPY":documentary_claim("JPY")}
                             if historical is None else historical))
        self.assertEqual(o["operational_bias"],"AGUARDAR")
        self.assertFalse(o["trade_authorized"])
        self.assertFalse(o["publishable"])
        self.assertIsNone(o["calibrated_probability"])
        self.assertIsNone(o["directional_bias"])
        self.assertEqual(o["signed_fx_macro_direction_effects_accepted"],0)
        self.assertFalse(o["authenticated_issuer_origin"])
        return o
    def test_seven_any_sources_not_seven_current(self):
        x=self.run_overlay()
        self.assertEqual(x["state"],"LAB_FX28_DOCUMENTARY_OVERLAY_RECONCILED_NO_GO")
        self.assertEqual(x["current_issuer_current_page_accepted_count"],5)
        self.assertEqual(x["historical_release_document_checked_count"],2)
        self.assertEqual(x["currencies_with_any_checked_policy_document_count"],7)
        self.assertEqual(x["pairs_with_both_any_checked_policy_documents_count"],21)
        self.assertEqual(x["pairs_with_both_current_policy_source_packets_count"],10)
        self.assertEqual(x["missing_any_policy_document_currencies"],["NZD"])
        self.assertEqual(len(x["pair_document_coverage"]),28)
    def test_issuer_release_metadata_cannot_promote_current_banks(self):
        x=self.run_overlay()
        rows=x["pair_document_coverage"]
        c=next(x for x in rows if x["pair"]=="USD/CHF")
        self.assertFalse(c["both_have_current_source_accepted"])
        self.assertTrue(c["both_have_some_checked_document"])
        self.assertIn("historical_policy_statement",
                      [c["document_type_base"],c["document_type_quote"]])
        n=next(x for x in rows if x["pair"]=="NZD/USD")
        self.assertFalse(n["both_have_some_checked_document"])
        self.assertFalse(n["signed_direction_allowed"])
    def test_empty_history_stays_five(self):
        x=self.run_overlay({})
        self.assertEqual(x["currencies_with_any_checked_policy_document_count"],5)
        self.assertEqual(x["pairs_with_both_any_checked_policy_documents_count"],10)
    def test_one_history_added_six_currencies(self):
        x=self.run_overlay({"CHF":documentary_claim("CHF")})
        self.assertEqual(x["currencies_with_any_checked_policy_document_count"],6)
        self.assertEqual(x["pairs_with_both_any_checked_policy_documents_count"],15)
    def test_wrong_sha_rejected(self):
        h={"CHF":documentary_claim("CHF"),"JPY":documentary_claim("JPY")}
        h["CHF"]["sha256"]="0"*64
        x=self.run_overlay(h)
        self.assertEqual(x["new_historical_docs_rejected"].get("CHF"),
                         "HISTORICAL_RELEASE_PIN_OR_SEMANTICS_REJECTED")
        self.assertEqual(x["currencies_with_any_checked_policy_document_count"],6)
    def test_changed_rate_rejected(self):
        h={"CHF":documentary_claim("CHF"),"JPY":documentary_claim("JPY")}
        h["CHF"]["document"]["rate_pct"]=1.0
        self.assertEqual(self.run_overlay(h)["historical_release_document_checked_count"],1)
    def test_jpy_defeated_dissent_not_target(self):
        h={"JPY":documentary_claim("JPY")}
        h["JPY"]["document"]["rate_target_pct"]=1.5
        x=self.run_overlay(h)
        self.assertEqual(x["historical_release_document_checked_count"],0)
    def test_jpy_false_vote_rejected(self):
        h={"JPY":documentary_claim("JPY")}
        h["JPY"]["document"]["decision_vote_for"]=1
        self.assertEqual(self.run_overlay(h)["historical_release_document_checked_count"],0)
    def test_wrong_issuer_url_rejected(self):
        h={"CHF":documentary_claim("CHF")}
        h["CHF"]["source_url"]="https://not-issuer.invalid"
        self.assertEqual(self.run_overlay(h)["historical_release_document_checked_count"],0)
    def test_wrong_byte_count_rejected(self):
        h={"JPY":documentary_claim("JPY")}
        h["JPY"]["bytes"]+=1
        self.assertEqual(self.run_overlay(h)["historical_release_document_checked_count"],0)
    def test_false_claim_of_independent_authentication_rejected(self):
        h={"CHF":documentary_claim("CHF")}
        h["CHF"]["release_first_seen_authenticated"]=True
        self.assertEqual(self.run_overlay(h)["historical_release_document_checked_count"],0)
    def test_wrong_retrieval_temporality_rejected(self):
        h={"CHF":documentary_claim("CHF")}
        h["CHF"]["retrieved_after_original_release"]=False
        self.assertEqual(self.run_overlay(h)["historical_release_document_checked_count"],0)
    def test_nzd_cannot_be_forged_as_chf_jpy_release(self):
        result=self.run_overlay({"NZD":documentary_claim("CHF")})
        self.assertEqual(result["state"],"LAB_FX28_HISTORICAL_OVERLAY_BLOCKED_NO_GO")
    def test_no_forecast_even_eight_current_proclaimed(self):
        x=self.run_overlay(
            {},{**baseline(CURRENCIES),
                "state":"LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO"})
        self.assertEqual(x["state"],"LAB_FX28_DOCUMENTARY_OVERLAY_RECONCILED_NO_GO")
        self.assertFalse(x["trade_authorized"])
        self.assertEqual(x["pairs_with_both_current_policy_source_packets_count"],28)

if __name__=="__main__":unittest.main(verbosity=2)
