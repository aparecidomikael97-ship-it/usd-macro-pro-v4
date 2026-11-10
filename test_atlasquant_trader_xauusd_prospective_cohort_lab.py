"""Gold D1/W1 complete prospective cohort: synthetic forecasts and prices only."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_mt5_xauusd_closedbar_capture_lab import (
    collect_xauusd_closedbar_snapshot_lab as collect,
)
from atlasquant_trader_xauusd_prospective_cohort_lab import (
    GoldDecision, assess_gold_two_horizon_outcomes_lab as assess,
    freeze_gold_two_horizon_cohort_lab as freeze,
)
from test_atlasquant_mt5_xauusd_closedbar_capture_lab import (
    AT, FakeMT5, WIN_TERMINAL,
)

PLAN = AT - timedelta(days=10)
LOCK = AT - timedelta(days=8)
DECIDED = AT - timedelta(days=9)


def plans():
    return {
        "D1": (AT - timedelta(days=1), AT),
        "W1": (AT - timedelta(days=7), AT),
    }


def decisions():
    return (
        GoldDecision("D1", "UP", DECIDED, DECIDED,
                     "atlas_lab_v1", "a" * 64, None),
        GoldDecision("W1", "ABSTAIN", DECIDED, DECIDED,
                     "atlas_lab_v1", None, "NO_EDGE"),
    )


class GoldProspectiveCohortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gold_cohort_synthetic_")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "AtlasQuant" / "LAB" / "MT5_Snapshots"
        self.terminal = FakeMT5()
        collected = collect(self.terminal, terminal_path=WIN_TERMINAL,
                            output_root=root, clock=lambda: AT)
        self.assertEqual(collected["verified_local_bars"], 3700)
        self.archive = Path(collected["directory"])

    def frozen(self, **kwargs):
        fields = dict(cohort_id="GOLDNOV2026", target_windows=plans(),
                      decisions=decisions(), planned_at_utc=PLAN,
                      frozen_at_utc=LOCK, model_version="atlas_lab_v1")
        fields.update(kwargs)
        return freeze(**fields)

    def evaluate(self, recorded, *, archive=None, evaluated=AT):
        return assess(recorded["local_precommit_json"],
                      recorded["local_precommit_sha256"],
                      outcome_archive=self.archive if archive is None else archive,
                      evaluated_at_utc=evaluated)

    def no_trade(self, result):
        self.assertFalse(result["external_prediction_timestamp_authenticated"])
        self.assertFalse(result["source_vintages_authenticated"])
        self.assertFalse(result["broker_candles_authenticated"])
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertFalse(result["out_of_sample_accuracy_validated"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["can_feed_live_radar"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["file_writes"], 0)

    def test_two_slot_roster_freezes_direction_and_abstention(self):
        r = self.frozen()
        self.assertEqual(r["state"], "LAB_GOLD_TWO_SLOT_FORECAST_FROZEN_UNATTESTED")
        self.assertEqual(r["slots_expected"], 2)
        self.assertEqual(r["slots_verified"], 2)
        self.assertEqual(r["directional_claims"], 1)
        self.assertEqual(r["abstentions"], 1)
        record = json.loads(r["local_precommit_json"])
        self.assertEqual([x["horizon"] for x in record["slots"]], ["D1", "W1"])
        self.assertEqual([x["side_claim"] for x in record["slots"]], ["UP", "ABSTAIN"])
        self.assertEqual(sha256(r["local_precommit_json"].encode()).hexdigest(),
                         r["local_precommit_sha256"])
        self.no_trade(r)

    def test_future_closed_bars_resolve_complete_cohort_documentary_only(self):
        record = self.frozen()
        result = self.evaluate(record)
        self.assertEqual(result["state"],
                         "LAB_GOLD_TWO_HORIZON_OUTCOMES_DOCUMENTARY_NO_GO")
        self.assertTrue(result["archived_gold_outcomes_checked"])
        self.assertEqual(result["slots_verified"], 2)
        self.assertEqual(result["documentary_directional_trials"], 1)
        self.assertEqual(result["documentary_directional_matches"], 1)
        self.assertEqual(result["documentary_outcomes_by_horizon"]["D1"]["observed_candle_body_documentary"], "UP")
        self.assertIsNone(result["documentary_outcomes_by_horizon"]["W1"]["documentary_match_only"])
        self.no_trade(result)

    def test_both_directional_trials_keep_misses_in_denominator(self):
        d = list(decisions())
        d[-1] = GoldDecision("W1", "DOWN", DECIDED, DECIDED,
                             "atlas_lab_v1", "b" * 64, None)
        result = self.evaluate(self.frozen(decisions=tuple(d)))
        self.assertEqual(result["documentary_directional_trials"], 2)
        self.assertEqual(result["documentary_directional_matches"], 1)
        self.assertIs(result["documentary_outcomes_by_horizon"]["W1"]["documentary_match_only"], False)
        self.no_trade(result)

    def test_two_abstentions_are_preserved_not_counted_as_predictions(self):
        d = list(decisions())
        d[0] = GoldDecision("D1", "ABSTAIN", DECIDED, DECIDED,
                            "atlas_lab_v1", None, "MISSING_DATA")
        result = self.evaluate(self.frozen(decisions=tuple(d)))
        self.assertEqual(result["documentary_directional_trials"], 0)
        self.assertEqual(result["documentary_directional_matches"], 0)
        self.assertFalse(result["out_of_sample_accuracy_validated"])

    def test_missing_w1_decision_blocks_entire_roster(self):
        r = self.frozen(decisions=decisions()[:1])
        self.assertEqual(r["state"], "LAB_GOLD_PROSPECTIVE_COHORT_BLOCKED")
        self.assertEqual(r["slots_verified"], 0)

    def test_duplicate_decision_horizon_blocks_entire_roster(self):
        r = self.frozen(decisions=(decisions()[0], decisions()[0]))
        self.assertEqual(r["reason"], "DUPLICATE_OR_INVALID_GOLD_DECISION")

    def test_prediction_frozen_after_weekly_candle_begins_blocks(self):
        r = self.frozen(frozen_at_utc=AT - timedelta(days=6))
        self.assertEqual(r["reason"], "TARGET_OR_FORECAST_AFTER_START_OR_EVIDENCE_LEAKAGE")

    def test_feature_clock_after_decision_is_rejected(self):
        d = list(decisions())
        d[0] = GoldDecision("D1", "UP", DECIDED, DECIDED + timedelta(minutes=1),
                            "atlas_lab_v1", "a" * 64, None)
        self.assertEqual(self.frozen(decisions=d)["state"],
                         "LAB_GOLD_PROSPECTIVE_COHORT_BLOCKED")

    def test_direction_without_source_hash_is_rejected(self):
        d = list(decisions())
        d[0] = GoldDecision("D1", "UP", DECIDED, DECIDED,
                            "atlas_lab_v1", None, None)
        self.assertEqual(self.frozen(decisions=d)["reason"],
                         "DIRECTIONAL_FORECAST_EVIDENCE_CLAIM_INVALID")

    def test_abstention_requires_reason_and_no_hash(self):
        d = list(decisions())
        d[1] = GoldDecision("W1", "ABSTAIN", DECIDED, DECIDED,
                            "atlas_lab_v1", None, None)
        self.assertEqual(self.frozen(decisions=d)["reason"],
                         "ABSTENTION_REASON_OR_HASH_INVALID")

    def test_unhashable_abstention_reason_is_blocked_without_exception(self):
        d = list(decisions())
        d[1] = GoldDecision("W1", "ABSTAIN", DECIDED, DECIDED,
                            "atlas_lab_v1", None, ["NO_EDGE"])
        self.assertEqual(self.frozen(decisions=d)["reason"],
                         "ABSTENTION_REASON_OR_HASH_INVALID")

    def test_invalid_unicode_precommit_is_blocked_without_exception(self):
        r = assess("\ud800", "a" * 64,
                   outcome_archive=self.archive, evaluated_at_utc=AT)
        self.assertEqual(r["reason"], "LOCAL_PRECOMMIT_RECEIPT_INVALID_OR_CHANGED")

    def test_modified_forecast_blob_without_updated_hash_is_blocked(self):
        record = self.frozen()
        tampered = record["local_precommit_json"].replace('"side_claim":"UP"',
                                                          '"side_claim":"DOWN"')
        r = assess(tampered, record["local_precommit_sha256"],
                   outcome_archive=self.archive, evaluated_at_utc=AT)
        self.assertEqual(r["reason"], "LOCAL_PRECOMMIT_RECEIPT_INVALID_OR_CHANGED")
        self.no_trade(r)

    def test_changed_forecast_and_recomputed_local_hash_not_external_proof(self):
        record = self.frozen()
        tampered = record["local_precommit_json"].replace('"side_claim":"UP"',
                                                          '"side_claim":"DOWN"')
        # A caller can rewrite both local fields retrospectively: even if the
        # final hash is valid, none of the outputs qualify as real accuracy.
        r = assess(tampered, sha256(tampered.encode()).hexdigest(),
                   outcome_archive=self.archive, evaluated_at_utc=AT)
        self.assertEqual(r["state"], "LAB_GOLD_TWO_HORIZON_OUTCOMES_DOCUMENTARY_NO_GO")
        self.assertEqual(r["documentary_directional_matches"], 0)
        self.no_trade(r)

    def test_future_archive_must_be_available_at_evaluation(self):
        r = self.evaluate(self.frozen(), evaluated=AT - timedelta(seconds=1))
        self.assertEqual(r["reason"], "OUTCOME_ARCHIVE_NOT_AVAILABLE_AT_EVALUATION")

    def test_declared_target_candle_missing_blocks_all_outcomes(self):
        windows = plans()
        windows["D1"] = (AT - timedelta(days=2, seconds=-1),
                         AT - timedelta(days=1, seconds=-1))
        r = self.evaluate(self.frozen(target_windows=windows))
        self.assertTrue(r["reason"].startswith("DECLARED_GOLD_OUTCOME_UNRESOLVED:"))
        self.assertEqual(r["documentary_outcomes_by_horizon"], {})
        self.no_trade(r)

    def test_unclosed_future_target_does_not_resolve(self):
        windows = plans()
        windows["D1"] = (AT + timedelta(days=1), AT + timedelta(days=2))
        r = self.evaluate(self.frozen(target_windows=windows))
        self.assertEqual(r["reason"], "TARGET_CANDLE_NOT_CLOSED_BEFORE_OUTCOME_CAPTURE")

    def test_corrupt_outcome_archive_blocks_entire_denominator(self):
        (self.archive / "XAUUSD_W1_closedbar.csv.gz").write_bytes(b"broken")
        r = self.evaluate(self.frozen())
        self.assertEqual(r["reason"], "FUTURE_GOLD_ARCHIVE_INTEGRITY_FAILED")
        self.assertEqual(r["documentary_outcomes_by_horizon"], {})

    def test_no_write_or_mt5_calls_while_assessing(self):
        before = {p.name: sha256(p.read_bytes()).hexdigest()
                  for p in self.archive.iterdir()}
        api_calls_before = list(self.terminal.calls)
        self.evaluate(self.frozen())
        after = {p.name: sha256(p.read_bytes()).hexdigest()
                 for p in self.archive.iterdir()}
        self.assertEqual(before, after)
        self.assertEqual(api_calls_before, self.terminal.calls)


if __name__ == "__main__":
    unittest.main()
