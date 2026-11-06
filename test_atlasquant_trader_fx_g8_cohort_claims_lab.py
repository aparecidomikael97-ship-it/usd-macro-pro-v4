"""Synthetic-only receipt claims; none count as witnessed predictions."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import unittest

from atlasquant_trader_fx_g8_cohort_claims_lab import (
    KIND, MODEL, SCHEMA, inspect_g8_cohort_claims_lab as inspect,
)

COHORT = Path(__file__).resolve().parent.joinpath(
    "docs/continuidade/TRADER_G8_20261108_D1W1_FROZEN_COHORT_LAB.json"
).read_bytes()
MANIFEST = json.loads(COHORT)
NOW = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def entry(slot, *, direction="AGUARDAR"):
    return {
        "slot_id": slot["slot_id"], "pair": slot["pair"],
        "horizon": slot["horizon"], "direction_claim": direction,
        "created_at_utc": "2026-11-06T14:10:00Z",
        "data_cutoff_utc": ("2026-11-06T14:00:00Z" if direction != "AGUARDAR" else None),
        "model_version": MODEL if direction != "AGUARDAR" else None,
        "evidence_sha256": "a" * 64 if direction != "AGUARDAR" else None,
        "abstention_reason": "INSUFFICIENT_PIT_MACRO" if direction == "AGUARDAR" else None,
    }


def claims(*rows):
    return {
        "schema": SCHEMA, "research_kind": KIND,
        "cohort_id": MANIFEST["cohort_id"],
        "cohort_sha256": sha256(COHORT).hexdigest(), "entries": list(rows),
    }


def checked(obj, *, at=NOW, cohort=COHORT):
    return inspect(cohort_raw=cohort, claims_raw=encoded(obj), inspected_at_utc=at)


class CohortClaimsLabTests(unittest.TestCase):
    def assert_no_operational_promotion(self, r):
        for k in ("independent_external_precommit_witness_verified",
                  "source_publication_times_verified", "macro_data_point_in_time_verified",
                  "algorithm_frozen_before_forecasts_verified",
                  "future_price_outcomes_verified", "can_feed_live_radar",
                  "trade_authorized", "worker_enabled", "scheduler_enabled",
                  "publishable"):
            self.assertIs(r[k], False, k)
        self.assertTrue(r["claim_creation_times_self_declared"])
        self.assertTrue(r["macro_evidence_hashes_self_declared"])
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["probability_calibrated"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))

    def test_one_declared_abstention_does_not_become_a_predicted_win(self):
        report = checked(claims(entry(MANIFEST["slots"][0])))
        self.assertEqual(report["state"], "LAB_CLAIMS_STAGED_BEFORE_DEADLINE_UNATTESTED")
        self.assertEqual(report["submitted_slots"], 1)
        self.assertEqual(report["missing_slots"], 55)
        self.assertEqual(report["await_abstentions"], 1)
        self.assertEqual(report["directional_claims"], 0)
        self.assertEqual(report["coverage_fraction"], 1 / 56)
        self.assert_no_operational_promotion(report)

    def test_all_56_await_no_claims_or_proof_of_accuracy(self):
        report = checked(claims(*(entry(s) for s in MANIFEST["slots"])))
        self.assertEqual(report["submitted_slots"], 56)
        self.assertEqual(report["missing_slots"], 0)
        self.assertEqual(report["await_abstentions"], 56)
        self.assertEqual(report["directional_claims"], 0)
        self.assertEqual(report["coverage_fraction"], 1.0)
        self.assert_no_operational_promotion(report)

    def test_neutral_is_an_abstention_not_a_directional_hit(self):
        report = checked(claims(entry(MANIFEST["slots"][0], direction="NEUTRO")))
        self.assertEqual(report["neutral_abstentions"], 1)
        self.assertEqual(report["directional_claims"], 0)
        self.assert_no_operational_promotion(report)

    def test_directional_claims_remain_unattested(self):
        report = checked(claims(entry(MANIFEST["slots"][0], direction="ALTA")))
        self.assertEqual(report["directional_claims"], 1)
        self.assertEqual(report["validated_prediction_count"], 0)
        self.assert_no_operational_promotion(report)

    def test_identifies_cross_horizon_agreement_and_disagreement(self):
        d1 = next(s for s in MANIFEST["slots"] if s["pair"] == "EUR/USD" and s["horizon"] == "D1")
        w1 = next(s for s in MANIFEST["slots"] if s["pair"] == "EUR/USD" and s["horizon"] == "W1")
        a = checked(claims(entry(d1, direction="ALTA"), entry(w1, direction="BAIXA")))
        b = checked(claims(entry(d1, direction="ALTA"), entry(w1, direction="ALTA")))
        self.assertEqual(a["opposed_d1_w1_pairs"], ["EUR/USD"])
        self.assertEqual(a["aligned_d1_w1_pairs"], [])
        self.assertEqual(b["aligned_d1_w1_pairs"], ["EUR/USD"])
        self.assertEqual(b["opposed_d1_w1_pairs"], [])
        self.assert_no_operational_promotion(a)

    def test_await_on_w1_is_not_a_confirmation_of_d1(self):
        d1 = next(s for s in MANIFEST["slots"] if s["pair"] == "EUR/USD" and s["horizon"] == "D1")
        w1 = next(s for s in MANIFEST["slots"] if s["pair"] == "EUR/USD" and s["horizon"] == "W1")
        report = checked(claims(entry(d1, direction="ALTA"), entry(w1)))
        self.assertEqual(report["aligned_d1_w1_pairs"], [])
        self.assertEqual(report["opposed_d1_w1_pairs"], [])

    def test_wrong_cohort_sha_or_id_is_rejected(self):
        for k, v in (("cohort_sha256", "b" * 64), ("cohort_id", "ANOTHER")):
            obj = claims(entry(MANIFEST["slots"][0]))
            obj[k] = v
            report = checked(obj)
            self.assertEqual(report["reason"], "CLAIMS_NOT_BOUND_TO_EXACT_COHORT_BYTES")
            self.assert_no_operational_promotion(report)

    def test_duplicate_slots_cannot_inflate_coverage(self):
        row = entry(MANIFEST["slots"][0])
        report = checked(claims(row, deepcopy(row)))
        self.assertEqual(report["reason"], "UNKNOWN_OR_DUPLICATE_SLOT")
        self.assert_no_operational_promotion(report)

    def test_mismatched_pair_horizon_or_slot_identity_rejected(self):
        for key, value in (("pair", "USD/JPY"), ("horizon", "W1"),
                           ("slot_id", "G8_FAKE_USDJPY_D1")):
            row = entry(MANIFEST["slots"][0])
            row[key] = value
            self.assertEqual(checked(claims(row))["state"], "LAB_BLOCKED")

    def test_bad_future_and_post_deadline_claim_times_rejected(self):
        for stamp in ("2026-11-06T13:49:59Z", "2026-11-06T16:00:00Z",
                      "2026-11-08T21:00:01Z",
                      "2026-11-06 14:10:00", "2026-02-30T14:10:00Z"):
            row = entry(MANIFEST["slots"][0])
            row["created_at_utc"] = stamp
            self.assertEqual(checked(claims(row))["reason"],
                             "CLAIM_CREATION_NOT_BEFORE_PRECOMMIT_DEADLINE")

    def test_cutoff_after_created_and_unknown_model_rejected(self):
        for field, value in (("data_cutoff_utc", "2026-11-06T14:11:00Z"),
                             ("model_version", "LAB_TUNED_AFTER_RESULTS"),
                             ("evidence_sha256", "bad"),
                             ("abstention_reason", "PROFIT")):
            row = entry(MANIFEST["slots"][0], direction="ALTA")
            row[field] = value
            self.assertEqual(checked(claims(row))["reason"],
                             "DIRECTION_OR_NEUTRAL_NEEDS_FROZEN_MODEL_AND_EVIDENCE")

    def test_await_must_not_smuggle_fake_evidence_or_claims(self):
        for field, value in (("data_cutoff_utc", "2026-11-06T14:00:00Z"),
                             ("model_version", MODEL), ("evidence_sha256", "a" * 64),
                             ("abstention_reason", "WIN"),
                             ("abstention_reason", [])):
            row = entry(MANIFEST["slots"][0])
            row[field] = value
            self.assertEqual(checked(claims(row))["reason"],
                             "AWAIT_MUST_DECLARE_MISSING_EVIDENCE")

    def test_invalid_direction_and_extra_field_rejected(self):
        row = entry(MANIFEST["slots"][0])
        row["direction_claim"] = "COMPRA"
        self.assertEqual(checked(claims(row))["reason"], "CLAIM_DIRECTION_INVALID")
        row = entry(MANIFEST["slots"][0])
        row["pnl"] = "100%"
        self.assertEqual(checked(claims(row))["reason"], "CLAIM_FIELDS_INVALID")

    def test_no_empty_or_57th_or_non_list_entries(self):
        for rows in ([], None, "fake", [entry(MANIFEST["slots"][0])] * 57):
            obj = claims()
            obj["entries"] = rows
            self.assertEqual(checked(obj)["reason"], "CLAIM_COUNT_OUT_OF_RANGE")

    def test_old_claims_inspected_after_deadline_are_not_external_proof(self):
        late = datetime(2026, 11, 9, 10, tzinfo=timezone.utc)
        report = checked(claims(entry(MANIFEST["slots"][0], direction="BAIXA")), at=late)
        self.assertEqual(report["state"], "LAB_ARCHIVAL_CLAIMS_AFTER_DEADLINE_UNATTESTED")
        self.assert_no_operational_promotion(report)

    def test_invalid_frozen_manifest_rejected_even_if_claims_look_good(self):
        changed = COHORT.replace(b'"declared_pair_count":28', b'"declared_pair_count":27')
        report = checked(claims(entry(MANIFEST["slots"][0])), cohort=changed)
        self.assertEqual(report["reason"], "FROZEN_COHORT_INVALID_OR_NOT_YET_CREATED")
        self.assert_no_operational_promotion(report)

    def test_duplicate_json_keys_nan_wrong_kind_or_bad_clock_rejected(self):
        obj = claims(entry(MANIFEST["slots"][0]))
        raw = encoded(obj)
        duplicates = raw[:-2] + b',"schema":"override"}'
        for candidate in (duplicates, b'{"schema": NaN}', b'not-json', b'\xff'):
            report = inspect(cohort_raw=COHORT, claims_raw=candidate, inspected_at_utc=NOW)
            self.assertEqual(report["state"], "LAB_BLOCKED")
        obj["research_kind"] = "REAL_VERIFIED_FORECASTS"
        self.assertEqual(checked(obj)["state"], "LAB_BLOCKED")
        self.assertEqual(inspect(cohort_raw=COHORT, claims_raw=raw,
                                 inspected_at_utc=datetime(2026, 11, 6, 15))["state"],
                         "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
