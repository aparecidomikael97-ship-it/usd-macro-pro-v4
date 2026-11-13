"""End-to-end documentary factor audit using true offline bank/BLS parsers.

All source bytes and macro impact claims are SYNTHETIC. Nothing in this
suite attests real issuer identities, CPI consensus, FX price or forecast.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_macro_relative_score_prototype_lab import (
    HypotheticalMacroFactorClaim as F,
)
from atlasquant_trader_fx28_32_factor_source_admission_lab import (
    SCHEMA, inspect_fx28_32_factor_source_admission_lab as inspect,
)
from atlasquant_trader_fx28_policy_ppi_unified_readiness_lab import (
    inspect_fx28_policy_ppi_readiness_lab as unified,
)
from atlasquant_trader_us_ppi_oct2026_original_capture_lab import (
    capture_oct2026_bls_original_once_lab as capture,
)
from atlasquant_trader_us_bls_cpi_u_nsa_yoy_capture_lab import (
    capture_bls_cpi_u_nsa_original_once_lab as cpi_capture,
)
from test_atlasquant_trader_us_bls_cpi_u_nsa_yoy_capture_lab import (
    Response as CpiResponse,
)
from test_atlasquant_trader_us_ppi_oct2026_original_capture_lab import (
    MockResponse, START, FINISH,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import raw
from test_atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    archive_dir, save_fixture,
)
from test_atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    synthetic_packets,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,14,5,tzinfo=UTC)
CATEGORIES=("policy_expectations","inflation_impact",
            "activity_impact","labor_impact")


class Fx28TrueSourceFactorAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank_sources=synthetic_packets()

    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def banks(self, currencies=()):
        folder=archive_dir(self.tmp.name)
        for c in currencies:
            save_fixture(folder,c,self.bank_sources[c])
        return folder

    def ppi(self):
        fake=Mock(return_value=MockResponse(
            body=raw(head="0.3",core="0.3",extra="0.5")))
        timer=Mock(side_effect=[START,FINISH])
        stored=capture(allow_one_get=True,local_appdata=self.tmp.name,
                       open_url=fake,clock=timer)
        self.assertTrue(stored["raw_bytes_and_receipt_replayed"])
        fake.assert_called_once()
        return stored["archive_directory_basename"]

    def cpi(self):
        transport=Mock(return_value=CpiResponse())
        started=NOW-timedelta(minutes=2)
        finished=started+timedelta(seconds=2)
        timer=Mock(side_effect=[started,finished])
        stored=cpi_capture(allow_one_get=True,local_appdata=self.tmp.name,
                           open_url=transport,clock=timer)
        self.assertTrue(stored["raw_original_bytes_retained_and_replayed_local_only"])
        transport.assert_called_once()
        return stored["archive_directory_basename"]

    def run_it(self,*,ppi=None,cpi=None,at=NOW,claims=None,root=None):
        return inspect(
            local_appdata=self.tmp.name if root is None else root,
            decision_at_utc=at,ppi_archive_basename=ppi,
            cpi_archive_basename=cpi,
            hypothetical_factors=claims)

    def guard(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["currency_count_expected"],8)
        self.assertEqual(r["factor_slots_expected"],32)
        self.assertEqual(r["pair_count_expected"],28)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for key in (
            "trade_authorized","publishable","live_alert_allowed",
            "scheduler_enabled","worker_enabled",
            "issuer_identity_and_first_seen_independently_attested",
            "historical_macro_point_in_time_authenticated",
            "bilateral_cpi_and_pre_event_consensus_authenticated",
            "rate_expectation_surprises_authenticated",
            "activity_and_labor_suprisal_effects_authenticated",
            "broker_m15_price_history_authenticated",
            "model_directional_effects_calibrated",
            "fx28_forecast_witnessed_before_window",
            "experimental_score_execution_authorized",
            "real_directional_forecast_authorized",
        ):
            self.assertFalse(r[key],key)
        self.assertEqual(r["factor_slots_with_signed_impact_independently_admissible"],0)
        self.assertEqual(r["factor_slots_with_pre_event_consensus_verified"],0)
        self.assertEqual(r["factor_slots_with_calibrated_directional_effect"],0)
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["validated_direction_accuracy"])
        self.assertTrue(r["ppi_is_one_shared_us_event_not_seven_independent_inflation_events"])
        self.assertTrue(r["ppi_actuals_are_not_cpi_consensus_or_usd_direction"])
        self.assertTrue(r["policy_rates_are_not_forward_policy_expectations"])
        self.assertTrue(r["hash_match_only_proves_local_byte_consistency"])
        self.assertEqual(r["network_requests"],0)
        self.assertEqual(r["file_writes"],0)
        self.assertEqual(r["new_cost_brl"],0)
        for slot in r["factor_slots"]:
            self.assertFalse(slot["source_semantics_support_signed_factor"])
            self.assertIsNone(slot["signed_impact_points_admitted"])
            self.assertFalse(slot["pre_event_consensus_independently_attested"])
        for pair in r["pairs"]:
            self.assertEqual(pair["operational_bias"],"AGUARDAR")
            self.assertFalse(pair["trade_authorized"])
            self.assertIsNone(pair["forecast_direction"])
            self.assertIsNone(pair["calibrated_probability"])
            self.assertEqual(pair["model_signed_factor_slots_admitted"],0)

    def audited(self,r):
        self.guard(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_32_FACTOR_DOCUMENTARY_GAP_RECONCILED_NO_GO")
        self.assertEqual(r["factor_slots_inspected"],32)
        self.assertEqual(len(r["factor_slots"]),32)
        self.assertEqual(len(r["pairs"]),28)
        self.assertEqual([x["pair"] for x in r["pairs"]],
                         list(OFFICIAL_PAIRS))
        self.assertEqual({(x["currency"],x["category"])
                          for x in r["factor_slots"]},
                         {(c,k) for c in CURRENCIES for k in CATEGORIES})

    def claims(self,*,source=None,ppi_sha=None):
        hashes={}
        if source is not None:
            ledger=source["policy_source_byte_sha_lineage_by_currency"]
            for c,doc in ledger.items():
                hashes[(c,"policy_expectations")]=doc[
                    "source_original_sha256_local_claim"]
        if ppi_sha:
            hashes[("USD","inflation_impact")]=ppi_sha
        result=[]
        for c in sorted(CURRENCIES):
            for k in CATEGORIES:
                digest=hashes.get(
                    (c,k),sha256((c+"-"+k).encode("ascii")).hexdigest())
                result.append(F(
                    currency=c,category=k,signed_impact_points=90,
                    event_published_at_utc=NOW-timedelta(minutes=25),
                    source_locally_captured_at_utc=NOW-timedelta(minutes=20),
                    event_root_id="EVENT."+c+"."+k.upper(),
                    source_sha256_claim=digest,
                ))
        return result

    def test_01_missing_local_folder_not_called_real_macroeconomic_data(self):
        report=self.run_it()
        self.audited(report)
        self.assertEqual(report["locally_replayed_policy_issuer_count"],0)
        self.assertEqual(report["locally_replayed_ppi_document_count"],0)
        self.assertEqual(report["factor_slots_with_any_relevant_local_document"],0)
        self.assertEqual(report["distinct_original_document_sha_claim_count"],0)
        self.assertTrue(all(x["documentary_source_kind"] is None
                            for x in report["factor_slots"]))

    def test_02_three_policy_rate_files_do_not_become_rate_expectations(self):
        self.banks(("USD","EUR","CAD"))
        report=self.run_it()
        self.audited(report)
        self.assertEqual(report["locally_replayed_policy_issuer_count"],3)
        self.assertEqual(report["factor_slots_with_any_relevant_local_document"],3)
        self.assertEqual(report["distinct_original_document_sha_claim_count"],3)
        present=[x for x in report["factor_slots"] if x["documentary_source_kind"]]
        self.assertEqual({x["currency"] for x in present},{"USD","EUR","CAD"})
        self.assertEqual({x["category"] for x in present},{"policy_expectations"})
        self.assertTrue(all(x["missing_model_input_reason"]==
            "POLICY_RATE_IS_NOT_FORWARD_RATE_EXPECTATIONS" for x in present))

    def test_03_eight_policy_files_are_still_zero_signed_factors(self):
        self.banks(CURRENCIES)
        report=self.run_it()
        self.audited(report)
        self.assertEqual(report["locally_replayed_policy_issuer_count"],8)
        self.assertEqual(report["factor_slots_with_any_relevant_local_document"],8)
        self.assertEqual(report["distinct_original_document_sha_claim_count"],8)
        self.assertEqual(sum(x["source_replayed_for_documentary_context_only"]
                            for x in report["factor_slots"]),8)
        self.assertFalse(report["model_directional_effects_calibrated"])

    def test_04_ppi_only_is_one_document_not_eight_currency_inflations(self):
        ppi=self.ppi()
        report=self.run_it(ppi=ppi)
        self.audited(report)
        self.assertEqual(report["locally_replayed_ppi_document_count"],1)
        self.assertEqual(report["locally_replayed_policy_issuer_count"],0)
        self.assertEqual(report["factor_slots_with_any_relevant_local_document"],1)
        self.assertEqual(report["distinct_original_document_sha_claim_count"],1)
        ppi_slots=[s for s in report["factor_slots"]
                   if s["documentary_source_kind"]=="BLS_PPI_OCT2026_ACTUAL_ONLY"]
        self.assertEqual(len(ppi_slots),1)
        self.assertEqual(ppi_slots[0]["currency"],"USD")
        self.assertEqual(ppi_slots[0]["category"],"inflation_impact")
        self.assertEqual(ppi_slots[0]["missing_model_input_reason"],
                         "BLS_PPI_ACTUAL_NOT_CPI_SURPRISE_OR_CURRENCY_EFFECT")

    def test_05_eight_banks_and_ppi_are_nine_documents_not_32_signed_impacts(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        report=self.run_it(ppi=ppi)
        self.audited(report)
        self.assertEqual(report["locally_replayed_policy_issuer_count"],8)
        self.assertEqual(report["locally_replayed_ppi_document_count"],1)
        self.assertEqual(report["distinct_original_document_sha_claim_count"],9)
        self.assertEqual(report["factor_slots_with_any_relevant_local_document"],9)
        self.assertFalse(report["real_directional_forecast_authorized"])

    def test_06_hypothetical_all_90_even_matching_nine_source_sha_is_no_go(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        source=unified(local_appdata=self.tmp.name,decision_at_utc=NOW,
                       ppi_archive_basename=ppi)
        claims=self.claims(source=source,ppi_sha=source["ppi_source_raw_sha256"])
        report=self.run_it(ppi=ppi,claims=claims)
        self.audited(report)
        self.assertTrue(report["hypothetical_factor_claims_provided"])
        self.assertTrue(report["hypothetical_factor_claims_structurally_valid"])
        self.assertEqual(report["hypothetical_claims_matching_local_original_sha_only"],9)
        self.assertEqual(report["hypothetical_claims_without_matching_documentary_source"],23)
        self.assertEqual(report["factor_slots_with_signed_impact_independently_admissible"],0)
        self.assertTrue(all(x["signed_impact_points_admitted"] is None
                            for x in report["factor_slots"]))

    def test_07_all_fabricated_32_claims_without_issuer_bytes_match_zero(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        claims=self.claims()
        report=self.run_it(ppi=ppi,claims=claims)
        self.audited(report)
        self.assertEqual(report["hypothetical_claims_matching_local_original_sha_only"],0)
        self.assertEqual(report["hypothetical_claims_without_matching_documentary_source"],32)
        self.assertFalse(report["experimental_score_execution_authorized"])

    def test_08_tamper_bank_source_removes_only_its_documentary_factor(self):
        folder=self.banks(CURRENCIES)
        originals=[x for x in folder.glob("CAD_BOC_*.json")
                   if not x.name.endswith(".receipt.json")]
        self.assertEqual(len(originals),1)
        originals[0].write_bytes(originals[0].read_bytes()+b"forged")
        report=self.run_it()
        self.audited(report)
        self.assertEqual(report["locally_replayed_policy_issuer_count"],7)
        self.assertEqual(report["factor_slots_with_any_relevant_local_document"],7)
        cad=next(x for x in report["factor_slots"]
                 if x["currency"]=="CAD" and x["category"]=="policy_expectations")
        self.assertIsNone(cad["documentary_source_sha256_local_claim"])

    def test_09_tamper_ppi_source_no_inflation_input_even_usd(self):
        ppi=self.ppi()
        file=(Path(self.tmp.name)/"AtlasQuant"/"LAB"/
              "official_macro_receipts"/ppi/"original.html")
        file.write_bytes(file.read_bytes()+b"forged")
        report=self.run_it(ppi=ppi)
        self.audited(report)
        self.assertEqual(report["locally_replayed_ppi_document_count"],0)
        usd=next(x for x in report["factor_slots"]
                 if x["currency"]=="USD" and x["category"]=="inflation_impact")
        self.assertIsNone(usd["documentary_source_sha256_local_claim"])

    def test_10_explicit_future_hypothesis_does_not_bypass_source_reader(self):
        cs=self.claims()
        cs[0]=F(**{**cs[0].__dict__,
                    "source_locally_captured_at_utc":NOW+timedelta(seconds=1)})
        report=self.run_it(claims=cs)
        self.guard(report)
        self.assertEqual(report["state"],
                         "LAB_FX28_32_FACTOR_ADMISSION_BLOCKED_NO_GO")
        self.assertEqual(report["factor_slots_inspected"],0)
        self.assertEqual(report["reason"],
                         "INVALID_OR_FUTURE_HYPOTHETICAL_FACTOR_CLAIMS")

    def test_11_duplicate_hypothetical_factor_prevented_before_source_replay(self):
        cs=self.claims()
        cs[1]=cs[0]
        report=self.run_it(claims=cs)
        self.guard(report)
        self.assertEqual(report["factor_slots_inspected"],0)
        self.assertEqual(report["reason"],
                         "INVALID_OR_FUTURE_HYPOTHETICAL_FACTOR_CLAIMS")

    def test_12_unknown_currency_or_category_invalid_claims(self):
        for key,value in (("currency","ZAR"),("category","fake_factor"),
                          ("source_sha256_claim","A"*64),
                          ("signed_impact_points",None),
                          ("signed_impact_points",101)):
            with self.subTest(key=key,value=value):
                claims=self.claims()
                claims[0]=F(**{**claims[0].__dict__,key:value})
                report=self.run_it(claims=claims)
                self.guard(report)
                self.assertEqual(report["factor_slots_inspected"],0)

    def test_13_future_and_naive_decision_clock_blocks_no_score(self):
        for time in (None,NOW.replace(tzinfo=None),
                     NOW.replace(microsecond=1),"2026-11-13T14:05:00Z"):
            with self.subTest(time=time):
                report=self.run_it(at=time)
                self.guard(report)
                self.assertEqual(report["factor_slots_inspected"],0)
                self.assertEqual(report["state"],
                                 "LAB_FX28_32_FACTOR_ADMISSION_BLOCKED_NO_GO")

    def test_14_synthetic_ppi_is_not_7_independent_usd_inflation_events(self):
        ppi=self.ppi()
        report=self.run_it(ppi=ppi)
        self.audited(report)
        self.assertEqual(sum(s["documentary_source_kind"]==
            "BLS_PPI_OCT2026_ACTUAL_ONLY" for s in report["factor_slots"]),1)
        self.assertEqual(report["factor_slots_with_signed_impact_independently_admissible"],0)
        self.assertTrue(report["ppi_is_one_shared_us_event_not_seven_independent_inflation_events"])

    def test_15_policy_document_recency_expired_still_not_a_signed_factor(self):
        self.banks(CURRENCIES)
        report=self.run_it(at=NOW+timedelta(days=3))
        self.audited(report)
        self.assertEqual(report["locally_replayed_policy_issuer_count"],8)
        self.assertEqual(report["factor_slots_with_signed_impact_independently_admissible"],0)
        self.assertFalse(report["historical_macro_point_in_time_authenticated"])

    def test_16_exact_28_pairs_all_waiting_despite_documentary_coverage(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        result=self.run_it(ppi=ppi)
        self.audited(result)
        self.assertEqual(sum("USD" in row["pair"] for row in result["pairs"]),7)
        self.assertEqual(sum(row[
            "ppi_is_post_release_context_on_direct_usd_leg_only"]
            for row in result["pairs"]),7)
        self.assertTrue(all(not row["model_all_eight_macro_factors_for_pair_authenticated"]
                            for row in result["pairs"]))

    def test_17_no_source_file_changed_by_reconciling_32_factor_slots(self):
        folder=self.banks(CURRENCIES)
        ppi=self.ppi()
        expected={p.name:sha256(p.read_bytes()).hexdigest()
                  for p in folder.iterdir() if p.is_file()}
        report=self.run_it(ppi=ppi)
        self.audited(report)
        actual={p.name:sha256(p.read_bytes()).hexdigest()
                for p in folder.iterdir() if p.is_file()}
        self.assertEqual(expected,actual)

    def test_18_reordering_input_claims_does_not_change_documentary_results(self):
        self.banks(("USD","EUR","CAD"))
        a=self.claims()
        b=list(reversed(deepcopy(a)))
        left=self.run_it(claims=a)
        right=self.run_it(claims=b)
        self.audited(left)
        self.assertEqual(left,right)
        self.assertEqual(a,self.claims())



    def test_19_cpi_api_original_levels_use_one_us_inflation_documentary_slot(self):
        cpi=self.cpi()
        r=self.run_it(cpi=cpi)
        self.audited(r)
        self.assertEqual(r["locally_replayed_policy_issuer_count"],0)
        self.assertEqual(r["locally_replayed_ppi_document_count"],0)
        self.assertEqual(r["locally_replayed_cpi_u_nsa_document_count"],1)
        self.assertEqual(r["cpi_u_nsa_oct2026_yoy_pct_documentary"],"3.185")
        self.assertEqual(r["distinct_original_document_sha_claim_count"],1)
        self.assertEqual(r["factor_slots_with_any_relevant_local_document"],1)
        us=next(x for x in r["factor_slots"]
                if x["currency"]=="USD" and x["category"]=="inflation_impact")
        self.assertEqual(us["documentary_source_kind"],
                         "BLS_CPI_U_NSA_OCT2026_YOY_LOCAL_CALCULATION_ONLY")
        self.assertEqual(us["missing_model_input_reason"],
                         "BLS_CPI_U_NSA_YOY_NOT_PRE_EVENT_CONSENSUS_OR_USD_IMPACT")
        self.assertFalse(us["source_semantics_support_signed_factor"])
        self.assertIsNone(r["calibrated_probability"])

    def test_20_eight_banks_ppi_and_cpi_are_ten_sources_but_nine_slots(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        cpi=self.cpi()
        result=self.run_it(ppi=ppi,cpi=cpi)
        self.audited(result)
        self.assertEqual(result["locally_replayed_policy_issuer_count"],8)
        self.assertEqual(result["locally_replayed_ppi_document_count"],1)
        self.assertEqual(result["locally_replayed_cpi_u_nsa_document_count"],1)
        self.assertEqual(result["distinct_original_document_sha_claim_count"],10)
        self.assertEqual(result["factor_slots_with_any_relevant_local_document"],9)
        self.assertEqual(result["factor_slots_with_signed_impact_independently_admissible"],0)
        self.assertFalse(result["experimental_score_execution_authorized"])

    def test_21_ppi_stays_contextual_and_cpi_preferred_for_us_inflation(self):
        ppi=self.ppi()
        a=self.run_it(ppi=ppi)
        cpi=self.cpi()
        b=self.run_it(ppi=ppi,cpi=cpi)
        self.audited(a)
        self.audited(b)
        us=lambda result:next(x for x in result["factor_slots"]
                              if x["currency"]=="USD"
                              and x["category"]=="inflation_impact")
        self.assertEqual(us(a)["documentary_source_kind"],
                         "BLS_PPI_OCT2026_ACTUAL_ONLY")
        self.assertEqual(us(b)["documentary_source_kind"],
                         "BLS_CPI_U_NSA_OCT2026_YOY_LOCAL_CALCULATION_ONLY")
        self.assertNotEqual(us(a)["documentary_source_sha256_local_claim"],
                            us(b)["documentary_source_sha256_local_claim"])
        self.assertEqual(b["locally_replayed_ppi_document_count"],1)
        self.assertIsNone(b["usd_strength_score"] if "usd_strength_score" in b else None)

    def test_22_corrupt_cpi_original_excludes_cpi_without_excluding_ppi(self):
        ppi=self.ppi()
        cpi=self.cpi()
        original=(Path(self.tmp.name)/"AtlasQuant"/"LAB"/
                  "official_macro_receipts"/cpi/"original.json")
        original.write_bytes(original.read_bytes()+b"\nunsafe")
        report=self.run_it(ppi=ppi,cpi=cpi)
        self.audited(report)
        self.assertEqual(report["locally_replayed_cpi_u_nsa_document_count"],0)
        self.assertEqual(report["locally_replayed_ppi_document_count"],1)
        usd=next(s for s in report["factor_slots"]
                 if s["currency"]=="USD" and s["category"]=="inflation_impact")
        self.assertEqual(usd["documentary_source_kind"],
                         "BLS_PPI_OCT2026_ACTUAL_ONLY")
        self.assertIsNone(report["cpi_u_nsa_oct2026_yoy_pct_documentary"])

    def test_23_cpi_archive_bad_name_or_future_receipt_remains_no_go(self):
        cpi=self.cpi()
        invalid=self.run_it(cpi="../"+cpi)
        self.audited(invalid)
        self.assertEqual(invalid["locally_replayed_cpi_u_nsa_document_count"],0)
        self.assertEqual(invalid["factor_slots_with_signed_impact_independently_admissible"],0)
        prior=self.run_it(cpi=cpi,at=NOW-timedelta(minutes=4))
        self.audited(prior)
        self.assertEqual(prior["locally_replayed_cpi_u_nsa_document_count"],0)
        self.assertTrue(prior["hash_match_only_proves_local_byte_consistency"])

    def test_24_source_calculation_even_if_cpi_sha_matches_claim_no_score(self):
        cpi=self.cpi()
        base=self.run_it(cpi=cpi)
        self.audited(base)
        usd=next(x for x in base["factor_slots"]
                 if x["currency"]=="USD" and x["category"]=="inflation_impact")
        sha=usd["documentary_source_sha256_local_claim"]
        claims=self.claims()
        for i,c in enumerate(claims):
            if c.currency=="USD" and c.category=="inflation_impact":
                claims[i]=F(**{**c.__dict__,"source_sha256_claim":sha})
                break
        matched=self.run_it(cpi=cpi,claims=claims)
        self.audited(matched)
        self.assertEqual(matched["hypothetical_claims_matching_local_original_sha_only"],1)
        self.assertEqual(matched["factor_slots_with_signed_impact_independently_admissible"],0)
        self.assertFalse(matched["real_directional_forecast_authorized"])


if __name__=="__main__":
    unittest.main()
