"""Only synthetic macro receipts: hash linking does not prove FX forecasts."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import unittest

from atlasquant_trader_fx_g8_claims_macro_binding_lab import (
    SCHEMA, inspect_g8_claims_macro_bytes_lab as inspect,
)
from atlasquant_trader_fx_g8_cohort_claims_lab import (
    KIND, MODEL, SCHEMA as CLAIMS_SCHEMA,
)
from atlasquant_trader_g8_macro_asof_lab import ENVELOPE

COHORT = Path(__file__).resolve().parent.joinpath(
    "docs/continuidade/TRADER_G8_20261108_D1W1_FROZEN_COHORT_LAB.json"
).read_bytes()
FROZEN = json.loads(COHORT)
NOW = datetime(2026, 11, 6, 16, 0, tzinfo=timezone.utc)
CREATED = "2026-11-06T15:10:00Z"
CUTOFF = "2026-11-06T15:00:00Z"


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def macro_object(pair, *, created=CREATED):
    base, quote = pair.split("/")
    return {
        "schema": ENVELOPE, "pair": pair, "decision_at_utc": created,
        "records": [{
            "currency": currency, "indicator": indicator,
            "observation_period": "2026-09", "value": "2.0",
            "published_at_utc": "2026-10-29T12:00:00Z",
            "captured_at_utc": "2026-10-29T12:05:00Z",
            "source_type": ("CENTRAL_BANK" if indicator == "POLICY_RATE"
                            else "OFFICIAL_STATISTICS_OFFICE"),
            "source_sha256": "a" * 64,
        } for currency in (base, quote)
            for indicator in ("CPI_YOY", "POLICY_RATE")],
    }


def row(slot, *, direction="ALTA", raw=None):
    return {
        "slot_id": slot["slot_id"], "pair": slot["pair"],
        "horizon": slot["horizon"], "direction_claim": direction,
        "created_at_utc": CREATED,
        "data_cutoff_utc": CUTOFF if direction != "AGUARDAR" else None,
        "model_version": MODEL if direction != "AGUARDAR" else None,
        "evidence_sha256": sha256(raw).hexdigest() if raw is not None else None,
        "abstention_reason": ("INSUFFICIENT_PIT_MACRO"
                              if direction == "AGUARDAR" else None),
    }


def ledger(entries):
    return encoded({
        "schema": CLAIMS_SCHEMA, "research_kind": KIND,
        "cohort_id": FROZEN["cohort_id"],
        "cohort_sha256": sha256(COHORT).hexdigest(),
        "entries": entries,
    })


def prepared(slot_index=0, *, direction="ALTA", mutate_macro=None):
    slot = FROZEN["slots"][slot_index]
    m = macro_object(slot["pair"])
    if mutate_macro:
        mutate_macro(m)
    raw = encoded(m)
    return slot, row(slot, direction=direction, raw=raw), raw


def run(entries, evidence, *, at=NOW, frozen=COHORT):
    return inspect(cohort_raw=frozen, claims_raw=ledger(entries),
                   macro_bytes_by_slot=evidence, inspected_at_utc=at)


class MacroBytesBindingTests(unittest.TestCase):
    def assert_hard_no_go(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        for key in (
            "macro_source_independently_authenticated",
            "source_publication_times_independently_verified",
            "point_in_time_macro_vintage_independently_verified",
            "external_precommit_timestamp_independently_witnessed",
            "model_calibration_verified", "independent_d1_w1_future_prices_verified",
            "can_feed_live_radar", "trade_authorized", "publishable",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertIs(result[key], False, key)
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["external_http_requests"], 0)
        self.assertEqual(result["new_cost_brl"], 0)

    def test_exact_hash_and_pit_metadata_are_only_structural(self):
        slot, claim, macro = prepared()
        r = run([claim], {slot["slot_id"]: macro})
        self.assertEqual(r["state"], "LAB_SUBMITTED_CLAIMS_MACRO_BYTES_BOUND_UNATTESTED")
        self.assertEqual(r["cohort_sha256"], sha256(COHORT).hexdigest())
        self.assertEqual(r["claims_sha256"], sha256(ledger([claim])).hexdigest())
        self.assertEqual(r["evidence_requiring_slots"], 1)
        self.assertEqual(r["macro_bytes_bound_slots"], 1)
        self.assertEqual(r["directional_claims"], 1)
        self.assertEqual(r["missing_slots"], 55)
        self.assertTrue(r["all_submitted_required_macro_bytes_hash_bound"])
        self.assertTrue(r["all_submitted_required_macro_times_consistent"])
        self.assertTrue(r["claims_still_before_precommit_deadline"])
        self.assertEqual(len(r["macro_binding_receipt_sha256"]), 64)
        self.assert_hard_no_go(r)

    def test_neutral_is_bound_abstention_not_successful_direction(self):
        slot, claim, macro = prepared(direction="NEUTRO")
        r = run([claim], {slot["slot_id"]: macro})
        self.assertEqual(r["neutral_abstentions"], 1)
        self.assertEqual(r["directional_claims"], 0)
        self.assertEqual(r["macro_bytes_bound_slots"], 1)
        self.assert_hard_no_go(r)

    def test_await_needs_no_evidence_and_is_not_a_prediction(self):
        slot = FROZEN["slots"][0]
        r = run([row(slot, direction="AGUARDAR")], {})
        self.assertEqual(r["state"], "LAB_ONLY_ABSTENTIONS_NO_MACRO_EVIDENCE_NEEDED")
        self.assertEqual(r["evidence_requiring_slots"], 0)
        self.assertEqual(r["macro_bytes_bound_slots"], 0)
        self.assertEqual(r["await_abstentions"], 1)
        self.assertEqual(r["directional_claims"], 0)
        self.assertIsNone(r["macro_binding_receipt_sha256"])
        self.assertFalse(r["all_submitted_required_macro_bytes_hash_bound"])
        self.assert_hard_no_go(r)

    def test_all_56_await_does_not_become_56_forecast_hits(self):
        entries = [row(s, direction="AGUARDAR") for s in FROZEN["slots"]]
        r = run(entries, {})
        self.assertEqual(r["submitted_slots"], 56)
        self.assertEqual(r["missing_slots"], 0)
        self.assertEqual(r["await_abstentions"], 56)
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertEqual(r["state"], "LAB_ONLY_ABSTENTIONS_NO_MACRO_EVIDENCE_NEEDED")
        self.assert_hard_no_go(r)

    def test_all_28_pairs_and_both_horizons_match_original_bytes(self):
        entries, evidence = [], {}
        for s in FROZEN["slots"]:
            raw = encoded(macro_object(s["pair"]))
            entries.append(row(s, raw=raw))
            evidence[s["slot_id"]] = raw
        r = run(entries, evidence)
        self.assertEqual(r["state"], "LAB_SUBMITTED_CLAIMS_MACRO_BYTES_BOUND_UNATTESTED")
        self.assertEqual(r["submitted_slots"], 56)
        self.assertEqual(r["macro_bytes_bound_slots"], 56)
        self.assertEqual(r["directional_claims"], 56)
        self.assert_hard_no_go(r)

    def test_missing_extra_wrong_type_and_oversized_evidence_are_blocked(self):
        slot, claim, macro = prepared()
        for evidence in ({}, {slot["slot_id"]: macro, "UNLISTED": macro},
                         {slot["slot_id"]: macro.decode()},
                         {slot["slot_id"]: b"x" * 1_000_001},
                         None, []):
            r = run([claim], evidence)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_hard_no_go(r)

    def test_altering_macro_bytes_breaks_link_even_if_json_is_valid(self):
        slot, claim, macro = prepared()
        edited = json.loads(macro)
        edited["records"][0]["value"] = "2.1"
        r = run([claim], {slot["slot_id"]: encoded(edited)})
        self.assertEqual(r["reason"], "MACRO_HASH_DOES_NOT_MATCH_CLAIMED_BYTES")
        self.assertEqual(r["first_failed_slot_id"], slot["slot_id"])
        self.assert_hard_no_go(r)

    def test_arbitrary_claimed_hash_fails(self):
        slot, claim, macro = prepared()
        claim["evidence_sha256"] = "f" * 64
        self.assertEqual(run([claim], {slot["slot_id"]: macro})["state"], "LAB_BLOCKED")

    def test_wrong_macro_pair_even_with_matching_sha_is_blocked(self):
        slot, claim, macro = prepared(mutate_macro=lambda m: m.update(pair="USD/JPY"))
        r = run([claim], {slot["slot_id"]: macro})
        self.assertEqual(r["reason"], "MACRO_PAIR_CLOCK_OR_TWO_SIDED_RECEIPTS_INVALID")
        self.assert_hard_no_go(r)

    def test_macro_decision_time_must_equal_claim_creation(self):
        slot, claim, macro = prepared(mutate_macro=lambda m: m.update(
            decision_at_utc="2026-11-06T15:09:00Z"))
        self.assertEqual(run([claim], {slot["slot_id"]: macro})["reason"],
                         "MACRO_PAIR_CLOCK_OR_TWO_SIDED_RECEIPTS_INVALID")

    def test_macro_release_after_created_is_blocked(self):
        def change(m):
            m["records"][0]["published_at_utc"] = "2026-11-06T15:11:00Z"
            m["records"][0]["captured_at_utc"] = "2026-11-06T15:12:00Z"
        slot, claim, macro = prepared(mutate_macro=change)
        self.assertEqual(run([claim], {slot["slot_id"]: macro})["state"],
                         "LAB_BLOCKED")

    def test_release_before_created_but_after_cutoff_is_rejected(self):
        def change(m):
            m["records"][0]["published_at_utc"] = "2026-11-06T15:01:00Z"
            m["records"][0]["captured_at_utc"] = "2026-11-06T15:05:00Z"
        slot, claim, macro = prepared(mutate_macro=change)
        r = run([claim], {slot["slot_id"]: macro})
        self.assertEqual(r["reason"], "MACRO_RELEASE_OR_CAPTURE_AFTER_CLAIMED_DATA_CUTOFF")

    def test_any_old_nonselected_record_after_cutoff_is_rejected(self):
        def change(m):
            old = deepcopy(m["records"][0])
            old["observation_period"] = "2026-08"
            old["captured_at_utc"] = "2026-11-06T15:04:00Z"
            m["records"].append(old)
        slot, claim, macro = prepared(mutate_macro=change)
        r = run([claim], {slot["slot_id"]: macro})
        self.assertEqual(r["reason"], "MACRO_RELEASE_OR_CAPTURE_AFTER_CLAIMED_DATA_CUTOFF")

    def test_missing_other_currency_macro_rejects_false_completeness(self):
        def change(m):
            m["records"] = [r for r in m["records"] if r["currency"] != "USD"]
        slot, claim, macro = prepared(mutate_macro=change)
        self.assertEqual(run([claim], {slot["slot_id"]: macro})["reason"],
                         "MACRO_PAIR_CLOCK_OR_TWO_SIDED_RECEIPTS_INVALID")

    def test_stale_indicators_do_not_pass_two_sided_requirement(self):
        def change(m):
            for r in m["records"]:
                r["published_at_utc"] = "2026-01-30T12:00:00Z"
                r["captured_at_utc"] = "2026-01-30T12:05:00Z"
        slot, claim, macro = prepared(mutate_macro=change)
        self.assertEqual(run([claim], {slot["slot_id"]: macro})["state"],
                         "LAB_BLOCKED")

    def test_duplicate_macro_json_field_and_nonfinite_are_blocked(self):
        slot, claim, macro = prepared()
        for corrupted in (
            macro.replace(b'"schema":', b'"schema":"duplicate","schema":', 1),
            macro.replace(b'"value":"2.0"', b'"value":NaN', 1),
        ):
            claim["evidence_sha256"] = sha256(corrupted).hexdigest()
            self.assertEqual(run([claim], {slot["slot_id"]: corrupted})["state"],
                             "LAB_BLOCKED")

    def test_unknown_or_mismatched_cohort_remains_blocked(self):
        slot, claim, macro = prepared()
        mutated = COHORT.replace(b'"declared_pair_count":28',
                                 b'"declared_pair_count":27')
        self.assertEqual(run([claim], {slot["slot_id"]: macro}, frozen=mutated)["state"],
                         "LAB_BLOCKED")

    def test_late_audit_preserves_archive_state_without_retroactive_proof(self):
        slot, claim, macro = prepared()
        r = run([claim], {slot["slot_id"]: macro},
                at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_SUBMITTED_CLAIMS_MACRO_BYTES_BOUND_UNATTESTED")
        self.assertFalse(r["claims_still_before_precommit_deadline"])
        self.assert_hard_no_go(r)


if __name__ == "__main__":
    unittest.main()
