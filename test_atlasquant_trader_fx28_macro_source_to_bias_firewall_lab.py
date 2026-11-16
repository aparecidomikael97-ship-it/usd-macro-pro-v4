"""Motor A 32-source-to-28-bias firewall, synthetic offline contract QA.

No live economic source, no broker, no MT5, no network or source writes.
The fixtures are NOT authenticated issuer/consensus/market evidence.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_32_factor_source_admission_lab import (
    SCHEMA as ADMISSION_SCHEMA,
)
from atlasquant_trader_fx28_macro_relative_score_prototype_lab import (
    SCHEMA as HYPOTHETICAL_SCHEMA,
)
from atlasquant_trader_fx28_macro_source_to_bias_firewall_lab import (
    SCHEMA, CATEGORIES,
    audit_macro_source_to_bias_firewall_lab as audit,
)
from test_atlasquant_trader_fx28_macro_relative_score_prototype_lab import (
    evaluate, samples, BEFORE, START,
)


def source_report(*, documentary_codes=()):
    documented=set(documentary_codes)
    rows=[]
    for currency in sorted(CURRENCIES):
        for category in CATEGORIES:
            exists=(currency,category) in documented
            rows.append({
                "currency":currency, "category":category,
                "documentary_source_kind": (
                    "SYNTHETIC_POLICY_RATE_NOT_EXPECTATIONS" if exists else None
                ),
                "documentary_source_sha256_local_claim": (
                    sha256(f"TEST:{currency}:{category}".encode()).hexdigest()
                    if exists else None
                ),
                "source_replayed_for_documentary_context_only":exists,
                "source_semantics_support_signed_factor":False,
                "pre_event_consensus_independently_attested":False,
                "signed_impact_points_admitted":None,
                "missing_model_input_reason":"NOT_CALIBRATED_OR_NOT_AUTHENTICATED",
                "source_sha_is_not_issuer_or_pit_attestation":True,
            })
    return {
        "schema":ADMISSION_SCHEMA,
        "state":"LAB_FX28_32_FACTOR_DOCUMENTARY_GAP_RECONCILED_NO_GO",
        "factor_slots_expected":32,
        "factor_slots_inspected":32,
        "factor_slots":rows,
        "pair_count_expected":28,
        "pairs":[{
            "pair":pair,"forecast_direction":None,
            "calibrated_probability":None,
            "trade_authorized":False,"operational_bias":"AGUARDAR",
            "model_signed_factor_slots_admitted":0,
        } for pair in OFFICIAL_PAIRS],
        "operational_bias":"AGUARDAR",
        "trade_authorized":False, "publishable":False,
        "experimental_score_execution_authorized":False,
        "real_directional_forecast_authorized":False,
        "model_directional_effects_calibrated":False,
        "issuer_identity_and_first_seen_independently_attested":False,
        "historical_macro_point_in_time_authenticated":False,
        "factor_slots_with_any_relevant_local_document":len(documented),
        "factor_slots_with_signed_impact_independently_admissible":0,
        "factor_slots_with_calibrated_directional_effect":0,
        "factor_slots_with_pre_event_consensus_verified":0,
        "calibrated_probability":None,
        "validated_direction_accuracy":None,
    }


def synthetic_score():
    # Generates hypothetical scores using the EXISTING V4 prototype.
    # This must not be used as a production currency bias or odds.
    return evaluate(
        horizon="D1",window_start_utc=START,calculated_at_utc=BEFORE,
        claimed_factors=samples(values={"USD":80,"EUR":-50}),
    )


class Fx28SourceBiasFirewallTests(unittest.TestCase):
    def setUp(self):
        self.source=source_report(documentary_codes=(
            ("EUR","policy_expectations"),("USD","policy_expectations"),
            ("USD","inflation_impact"),
        ))

    def checked(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertIsNone(r["directional_bias"])
        self.assertIsNone(r["calibrated_directional_probability"])
        self.assertIsNone(r["independently_validated_out_of_sample_accuracy"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["production_deployed"])
        self.assertFalse(r["source_replay_performed_by_this_module"])
        self.assertFalse(r["scorer_invoked_by_this_module"])
        self.assertEqual((r["http_requests"],r["mt5_calls"],r["file_writes"]),(0,0,0))
        self.assertEqual(r["new_cost_brl"],0)
        return r

    def blocked(self,r):
        self.checked(r)
        self.assertEqual(r["state"],
            "LAB_FX28_MACRO_SOURCE_TO_BIAS_FIREWALL_BLOCKED_NO_GO")
        self.assertEqual(r["factor_slots_validated"],0)
        self.assertEqual(r["hypothetical_labeled_pairs_quarantined"],0)
        return r

    def test_01_three_documentary_slots_are_not_three_signed_factors(self):
        r=self.checked(audit(admission_report=self.source))
        self.assertEqual(r["state"],
            "LAB_FX28_DOCUMENTARY_HYPOTHESIS_SEPARATION_VERIFIED_NO_GO")
        self.assertEqual(r["factor_slots_with_documentary_context"],3)
        self.assertEqual(r["factor_slots_without_documentary_context"],29)
        self.assertEqual(r["factor_slots_missing_consensus_or_effect_calibration"],32)
        self.assertEqual(r["factor_slots_with_independently_calibrated_signed_effect"],0)
        self.assertEqual(r["factor_slots_validated"],32)
        self.assertEqual(len(r["pairs"]),28)
        self.assertEqual(r["by_currency_factor_gaps"]["USD"]["inflation_impact"],
            "DOCUMENT_ONLY_NO_SIGNED_EFFECT")

    def test_02_all_32_documented_still_zero_calibrated(self):
        codes=[(currency,category)
               for currency in CURRENCIES for category in CATEGORIES]
        r=self.checked(audit(admission_report=source_report(documentary_codes=codes)))
        self.assertEqual(r["factor_slots_with_documentary_context"],32)
        self.assertEqual(r["factor_slots_without_documentary_context"],0)
        self.assertEqual(r["factor_slots_missing_consensus_or_effect_calibration"],32)
        self.assertFalse(r["complete_bilateral_factors_for_any_pair"])

    def test_03_no_sources_does_not_invent_missing_cpi_values(self):
        r=self.checked(audit(admission_report=source_report()))
        self.assertEqual(r["factor_slots_with_documentary_context"],0)
        self.assertEqual(r["factor_slots_without_documentary_context"],32)
        self.assertTrue(all(
            val=="NO_DOCUMENT_OR_ADMISSIBLE_EFFECT"
            for row in r["by_currency_factor_gaps"].values()
            for val in row.values()
        ))

    def test_04_hypothetical_13_labeled_pairs_never_live(self):
        h=synthetic_score()
        self.assertEqual(h["hypothetical_labeled_pair_count"],13)
        r=self.checked(audit(admission_report=self.source,
                             hypothetical_score_report=h))
        self.assertEqual(r["hypothetical_labeled_pairs_quarantined"],13)
        self.assertTrue(r["hypothetical_score_present"])
        self.assertEqual(len(r["pairs"]),28)
        self.assertTrue(all(row["bias"]=="AGUARDAR" and
                            row["directional_probability"] is None and
                            not row["trade_authorized"] for row in r["pairs"]))

    def test_05_fake_probability_in_macro_documentary_input_blocked(self):
        report=deepcopy(self.source);report["calibrated_probability"]=0.90
        self.blocked(audit(admission_report=report))

    def test_06_fake_one_source_signed_factor_blocks(self):
        report=deepcopy(self.source)
        report["factor_slots"][0]["signed_impact_points_admitted"]=87
        r=self.blocked(audit(admission_report=report))
        self.assertEqual(r["reason"],
            "SLOT_SOURCE_DOCUMENT_OR_SIGNED_EFFECT_CONTRADICTION")

    def test_06a_documentary_sha_must_be_real_lowercase_sha256_hex(self):
        for fake in ("z"*64, "G"*64, "0"*64, "a"*63, True, []):
            with self.subTest(fake=str(fake)[:40]):
                report=deepcopy(self.source)
                report["factor_slots"][0]["documentary_source_sha256_local_claim"]=fake
                result=self.blocked(audit(admission_report=report))
                self.assertEqual(result["reason"],
                                 "SLOT_SOURCE_DOCUMENT_OR_SIGNED_EFFECT_CONTRADICTION")

    def test_06b_source_kind_cannot_be_arbitrary_nonstring_or_control_text(self):
        for kind in ([], {"k":"v"}, 3, "", "FAKE SOURCE", "X\\nDANGER", "z"*129):
            with self.subTest(kind=str(kind)[:35]):
                report=deepcopy(self.source)
                report["factor_slots"][0]["documentary_source_kind"]=kind
                result=self.blocked(audit(admission_report=report))
                self.assertEqual(result["reason"],
                                 "SLOT_SOURCE_DOCUMENT_OR_SIGNED_EFFECT_CONTRADICTION")

    def test_07_document_count_7_cannot_be_8_with_only_7_documents(self):
        report=deepcopy(self.source)
        report["factor_slots_with_any_relevant_local_document"]=8
        r=self.blocked(audit(admission_report=report))
        self.assertEqual(r["reason"],
            "DOCUMENTARY_FACTOR_COUNT_INFLATED_OR_INCOMPLETE")

    def test_08_policy_rate_cannot_turn_into_forward_expectation(self):
        report=deepcopy(self.source)
        target=next(x for x in report["factor_slots"]
                    if x["currency"]=="USD"
                    and x["category"]=="policy_expectations")
        target["source_semantics_support_signed_factor"]=True
        self.blocked(audit(admission_report=report))

    def test_09_pretending_consensus_authenticated_blocks(self):
        report=deepcopy(self.source)
        report["factor_slots"][3]["pre_event_consensus_independently_attested"]=True
        self.blocked(audit(admission_report=report))

    def test_10_wrong_source_report_status_blocks(self):
        report=deepcopy(self.source);report["state"]="GO"
        self.blocked(audit(admission_report=report))

    def test_11_wrong_factor_order_blocks_no_prediction(self):
        report=deepcopy(self.source)
        report["factor_slots"].reverse()
        r=self.blocked(audit(admission_report=report))
        self.assertEqual(r["reason"],"INCOMPLETE_OR_REORDERED_32_FACTOR_ROSTER")

    def test_12_pair_roster_duplicate_blocks(self):
        report=deepcopy(self.source)
        report["pairs"][1]["pair"]=report["pairs"][0]["pair"]
        r=self.blocked(audit(admission_report=report))
        self.assertEqual(r["reason"],"INCOMPLETE_OR_REORDERED_28_PAIR_ROSTER")

    def test_13_fake_pair_direction_blocks(self):
        report=deepcopy(self.source)
        report["pairs"][0]["forecast_direction"]="BUY"
        self.blocked(audit(admission_report=report))

    def test_14_hypothetical_report_with_go_flag_blocks(self):
        h=synthetic_score()
        h["trade_authorized"]=True
        r=self.blocked(audit(admission_report=self.source,
                             hypothetical_score_report=h))
        self.assertEqual(r["reason"],"HYPOTHETICAL_REPORT_FAKE_GO_OR_INVALID_SHAPE")

    def test_15_hypothetical_report_false_probability_blocks(self):
        h=synthetic_score()
        h["calibrated_probability"]=0.99
        self.blocked(audit(admission_report=self.source,
                           hypothetical_score_report=h))

    def test_16_hypothetical_pair_with_trade_permission_blocks(self):
        h=synthetic_score()
        h["pairs"][0]["trade_authorized"]=True
        r=self.blocked(audit(admission_report=self.source,
                             hypothetical_score_report=h))
        self.assertEqual(r["reason"],"HYPOTHETICAL_PAIR_CONTAINS_LIVE_AUTHORIZATION")

    def test_17_hypothetical_label_count_forgery_blocks(self):
        h=synthetic_score()
        h["hypothetical_labeled_pair_count"]=28
        r=self.blocked(audit(admission_report=self.source,
                             hypothetical_score_report=h))
        self.assertEqual(r["reason"],"HYPOTHETICAL_LABEL_COUNT_INCONSISTENT")

    def test_18_unknown_or_malformed_source_is_denied(self):
        for bad in (None, [], "source", {},
                    {"schema":ADMISSION_SCHEMA}):
            with self.subTest(bad=bad):
                self.blocked(audit(admission_report=bad))

    def test_19_no_false_real_price_from_current_documentary_context(self):
        result=self.checked(audit(admission_report=self.source))
        self.assertFalse(result["issuer_origin_and_point_in_time_independently_verified"])
        self.assertTrue(result["source_sha_does_not_authenticate_publication_or_first_seen"])
        self.assertTrue(result["policy_rate_is_not_policy_expectation"])
        self.assertTrue(result["post_event_actual_is_not_pre_event_surprise"])
        self.assertFalse(result["monthly_bias_validated"])

    def test_20_admission_report_consistency_does_not_emit_m15_trade(self):
        r=self.checked(audit(admission_report=self.source))
        self.assertEqual(r["factor_slots_validated"],32)
        self.assertFalse(r["complete_bilateral_factors_for_any_pair"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertTrue(all(x["trade_authorized"] is False for x in r["pairs"]))


if __name__=="__main__":
    unittest.main(verbosity=2)
