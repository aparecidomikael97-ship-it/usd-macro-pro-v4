"""Synthetic tests: never evidence of trading accuracy or trusted timestamps."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx_forecast_precommit_lab import (
    ForecastPrecommitClaim, MacroVintageClaim, build_fx_precommit_chain_lab,
)
from atlasquant_trader_selective_event_root_oos_audit_lab import (
    FrozenOpportunityManifest, ObservedOpportunity, LABEL,
)
from atlasquant_trader_selective_precommit_bridge_lab import (
    reconcile_precommit_event_root_oos_lab as join,
)

T = timezone.utc
BASE = datetime(2026, 10, 1, 12, tzinfo=T)
NOW = BASE + timedelta(days=4)


def v(currency):
    return MacroVintageClaim(currency=currency, issuer_code="BLS",
                             release_id=f"CPI_{currency}_SEPT_2026",
                             published_at=BASE-timedelta(days=10),
                             captured_at=BASE-timedelta(days=9),
                             original_sha256_claim="f"*64)


def example():
    forecasts, observations = [], []
    for i, (oid, pair, side, correct) in enumerate((
        ("SLOT_00001", "EUR/USD", "UP", False),
        ("SLOT_00002", "USD/JPY", "DOWN", True),
    )):
        issued = BASE + timedelta(minutes=i)
        forecasts.append(ForecastPrecommitClaim(
            opportunity_id=oid, pair=pair, horizon="D1", side=side,
            abstain_reason=None, features_captured_at=issued-timedelta(hours=1),
            features_sha256_claim="a"*64,
            model_frozen_at=BASE-timedelta(days=2),
            model_sha256_claim="b"*64, prediction_issued_at=issued,
            outcome_start_at=issued+timedelta(days=1),
            outcome_end_at=issued+timedelta(days=2),
            macro_vintages=tuple(v(c) for c in pair.split("/"))))
        observations.append(ObservedOpportunity(
            opportunity_id=oid, asset=pair, horizon="D1",
            event_root_id="PPI_US_TEST", decided_at_utc=issued,
            issued_direction="ALTA" if side == "UP" else "BAIXA",
            outcome_observed_at_utc=issued+timedelta(days=2,minutes=1),
            correct_direction=correct, outcome_label=LABEL))
    plan = FrozenOpportunityManifest("CAMPAIGN_2026", "v1.0",
                                     BASE-timedelta(days=3),
                                     tuple(x.opportunity_id for x in forecasts))
    original = build_fx_precommit_chain_lab(forecasts, evaluated_at_utc=NOW)
    assert original["state"] == "LAB_PRECOMMIT_LOCAL_HASH_CHAIN_CREATED_UNATTESTED", original
    return plan, forecasts, original["chain_entries"], original["head_sha256_claim"], observations


class JoinTests(unittest.TestCase):
    def run_join(self, item=None):
        plan, rec, receipts, head, obs = example() if item is None else item
        return join(frozen_manifest=plan, forecast_records=rec,
                    receipt_entries=receipts, receipt_head_sha256=head,
                    observations=obs, inspected_at_utc=NOW)

    def safety(self, result):
        self.assertFalse(result["publishable"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["external_time_witness_verified"])
        self.assertFalse(result["original_decision_externally_attested"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_direction_probability"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")

    def blocked(self, test, reason):
        res = self.run_join(test)
        self.assertEqual(res["state"], "LAB_PRECOMMIT_OOS_JOIN_BLOCKED")
        self.assertEqual(res["reason"], reason)
        self.assertIsNone(res["descriptive_audit"])
        self.safety(res)

    def test_two_pairs_one_shared_event_consistent_but_no_go(self):
        out = self.run_join()
        self.assertEqual(out["matched_opportunities"], 2)
        self.assertTrue(out["local_receipt_chain_matches"])
        self.assertEqual(out["state"], "LAB_PRECOMMIT_OOS_JOIN_DOCUMENTARY_ONLY_NO_GO")
        self.assertEqual(out["descriptive_audit"]["signal_hit_rate_observed_unattested"], 0.5)
        self.assertEqual(out["descriptive_audit"]["claimed_event_root_count_issued"], 1)
        self.safety(out)

    def test_tampering_precommit_side_rejected(self):
        plan, rec, receipts, head, obs = example()
        rec[0] = replace(rec[0], side="DOWN")
        self.blocked((plan, rec, receipts, head, obs),
                     "PRECOMMIT_RECEIPTS_MISSING_TAMPERED_OR_INVALID")

    def test_changing_outcome_side_to_fake_win_rejected(self):
        plan, rec, receipts, head, obs = example()
        obs[0] = replace(obs[0], issued_direction="BAIXA", correct_direction=True)
        self.blocked((plan, rec, receipts, head, obs),
                     "PAIR_HORIZON_SIDE_OR_DECISION_TIME_CHANGED")

    def test_early_result_rejected_even_if_audit_itself_would_count(self):
        plan, rec, receipts, head, obs = example()
        obs[0] = replace(obs[0], outcome_observed_at_utc=BASE+timedelta(hours=1))
        self.blocked((plan, rec, receipts, head, obs),
                     "OUTCOME_NOT_OBSERVED_AFTER_PRECOMMITTED_TARGET_END")

    def test_missing_row_rejected_without_partial_hit_rate(self):
        plan, rec, receipts, head, obs = example()
        self.blocked((plan, rec, receipts, head, obs[:-1]),
                     "FORECAST_OR_OBSERVATION_CENSUS_INCOMPLETE")

    def test_pair_or_horizon_relabel_rejected(self):
        plan, rec, receipts, head, obs = example()
        for changed in (replace(obs[0], asset="GBP/USD"), replace(obs[0], horizon="W1")):
            self.blocked((plan, rec, receipts, head, [changed,obs[1]]),
                         "PAIR_HORIZON_SIDE_OR_DECISION_TIME_CHANGED")

    def test_issued_time_relabel_rejected(self):
        plan, rec, receipts, head, obs = example()
        obs[0] = replace(obs[0], decided_at_utc=obs[0].decided_at_utc+timedelta(seconds=1))
        self.blocked((plan, rec, receipts, head, obs),
                     "PAIR_HORIZON_SIDE_OR_DECISION_TIME_CHANGED")

    def test_complete_rewrite_still_cannot_claim_trusted_time(self):
        plan, rec, receipts, head, obs = example()
        rec[0] = replace(rec[0], side="DOWN")
        obs[0] = replace(obs[0], issued_direction="BAIXA")
        new = build_fx_precommit_chain_lab(rec, evaluated_at_utc=NOW)
        self.assertEqual(new["state"], "LAB_PRECOMMIT_LOCAL_HASH_CHAIN_CREATED_UNATTESTED")
        result = self.run_join((plan,rec,new["chain_entries"],new["head_sha256_claim"],obs))
        self.assertTrue(result["local_receipt_chain_matches"])
        self.assertFalse(result["original_decision_externally_attested"])
        self.safety(result)

    def test_abstention_no_fabricated_win(self):
        plan, rec, receipts, head, obs = example()
        rec[1] = replace(rec[1], side="ABSTAIN", abstain_reason="NO_EDGE",
                         macro_vintages=())
        new = build_fx_precommit_chain_lab(rec, evaluated_at_utc=NOW)
        obs[1] = replace(obs[1], issued_direction="AGUARDAR",
                         outcome_observed_at_utc=None, correct_direction=None,
                         outcome_label=None)
        report = self.run_join((plan,rec,new["chain_entries"],new["head_sha256_claim"],obs))
        self.assertEqual(report["descriptive_audit"]["abstained_count"],1)
        self.assertEqual(report["descriptive_audit"]["issued_count"],1)
        self.safety(report)

    def test_wrong_abstention_result_blocked(self):
        plan, rec, receipts, head, obs = example()
        rec[1] = replace(rec[1], side="ABSTAIN", abstain_reason="NO_EDGE",
                         macro_vintages=())
        new = build_fx_precommit_chain_lab(rec, evaluated_at_utc=NOW)
        obs[1] = replace(obs[1], issued_direction="AGUARDAR")
        self.blocked((plan,rec,new["chain_entries"],new["head_sha256_claim"],obs),
                     "ABSTENTION_RELABELED_AS_A_WIN")


if __name__ == "__main__":
    unittest.main()
