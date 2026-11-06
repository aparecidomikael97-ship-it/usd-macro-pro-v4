"""Prospective cohort registration tests. All 56 slots are UNFILLED, not signals."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_g8_frozen_cohort_lab import (
    SCHEMA, EXPECTED_COUNT,
    build_g8_forward_cohort_lab as build,
    serialize_g8_forward_cohort_lab as serialize,
    inspect_g8_forward_cohort_lab as inspect,
)

PLANNING_REFERENCE = datetime(2026, 11, 6, 13, 50, tzinfo=timezone.utc)
INSPECTED = datetime(2026, 11, 6, 14, 0, tzinfo=timezone.utc)
FIXTURE = (Path(__file__).resolve().parent / "docs" / "continuidade"
           / "TRADER_G8_20261108_D1W1_FROZEN_COHORT_LAB.json")


def raw():
    return serialize(planning_reference_utc=PLANNING_REFERENCE)


_UNSET = object()


def audit(payload=_UNSET, inspected=INSPECTED):
    # An explicitly supplied None must reach the validator and be rejected.
    return inspect(raw() if payload is _UNSET else payload,
                   inspected_at_utc=inspected)


class FrozenG8CohortTests(unittest.TestCase):
    def assert_no_go(self, obj):
        self.assertFalse(obj["commit_recorded_externally_before_market"])
        self.assertFalse(obj["external_commit_timestamp_verified"])
        self.assertFalse(obj["algorithm_version_independently_frozen"])
        self.assertFalse(obj["point_in_time_macro_sources_verified"])
        self.assertFalse(obj["broker_m15_prices_verified"])
        self.assertIsNone(obj["validated_accuracy"])
        self.assertEqual(obj["operational_bias"], "AGUARDAR")
        self.assertFalse(obj["trade_authorized"])
        self.assertFalse(obj["worker_enabled"])
        self.assertFalse(obj["scheduler_enabled"])
        self.assertEqual(obj["new_cost_brl"], 0)

    def test_exact_committed_manifest_is_generated_byte_for_byte(self):
        self.assertTrue(FIXTURE.is_file())
        fixed = FIXTURE.read_bytes()
        self.assertEqual(fixed, raw())
        self.assertEqual(fixed[-1:], b"\n")
        r = audit(fixed)
        self.assertEqual(r["state"],
                         "LAB_COHORT_STRUCTURE_VALID_BEFORE_DEADLINE_NO_FORECAST")
        self.assertEqual(r["manifest_sha256"], sha256(fixed).hexdigest())
        self.assert_no_go(r)

    def test_full_28_pair_by_two_horizon_universe_in_fixed_order(self):
        p = build(planning_reference_utc=PLANNING_REFERENCE)
        self.assertEqual(p["schema"], SCHEMA)
        self.assertEqual(p["declared_pair_count"], 28)
        self.assertEqual(p["declared_slot_count"], EXPECTED_COUNT)
        self.assertEqual(len(p["slots"]), 56)
        self.assertEqual(len({x["slot_id"] for x in p["slots"]}), 56)
        self.assertEqual(p["declared_horizons"], ["D1", "W1"])
        self.assertEqual(
            [(x["pair"], x["horizon"]) for x in p["slots"]],
            [(pair, horizon) for horizon in ("D1", "W1")
             for pair in OFFICIAL_PAIRS])

    def test_all_slots_empty_directions_abstentions_uncommitted(self):
        p = build(planning_reference_utc=PLANNING_REFERENCE)
        self.assertEqual(p["committed_predictions"], 0)
        self.assertEqual(p["committed_abstentions"], 0)
        self.assertEqual(p["unfilled_slots"], 56)
        for slot in p["slots"]:
            self.assertEqual(slot["state"], "SLOT_UNFILLED_NO_FORECAST")
            self.assertIsNone(slot["direction"])
            self.assertIsNone(slot["forecast_receipt_sha256"])
            self.assertIsNone(slot["independent_precommit_witness"])
        self.assertFalse(p["algorithm_version_frozen_and_attested"])
        self.assertFalse(p["historical_accuracy_verified"])
        self.assertFalse(p["trade_authorized"])

    def test_real_upcoming_ny_daily_and_weekly_windows_and_deadlines(self):
        p = build(planning_reference_utc=PLANNING_REFERENCE)
        self.assertEqual(p["cohort_id"], "LAB_G8_20261108_D1W1_V1")
        self.assertEqual(p["daily_window"], {
            "start_at_utc": "2026-11-08T22:00:00Z",
            "end_at_utc": "2026-11-09T22:00:00Z",
            "precommit_deadline_utc": "2026-11-08T21:00:00Z",
        })
        self.assertEqual(p["weekly_window"], {
            "start_at_utc": "2026-11-08T22:00:00Z",
            "end_at_utc": "2026-11-13T22:00:00Z",
            "precommit_deadline_utc": "2026-11-08T21:00:00Z",
        })
        self.assertTrue(p["coverage_policy"]["selection_after_outcome_prohibited"])
        self.assertTrue(p["coverage_policy"]["abstentions_must_be_counted_separately"])

    def test_inspector_does_not_count_unfilled_slots_as_predictions(self):
        r = audit()
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual(r["required_slots"], 56)
        self.assertEqual(r["unfilled_slots"], 56)
        self.assertEqual(r["forecast_directions_recorded"], 0)
        self.assertEqual(r["evaluable_predictions"], 0)
        self.assertTrue(r["all_56_slots_unmodified"])
        self.assertTrue(r["still_before_60_minute_precommit_deadline"])
        self.assert_no_go(r)

    def test_past_registration_deadline_never_claims_forecast(self):
        late = datetime(2026, 11, 8, 21, 0, 1, tzinfo=timezone.utc)
        r = audit(inspected=late)
        self.assertEqual(r["state"], "LAB_COHORT_STRUCTURE_VALID_BUT_DEADLINE_PASSED")
        self.assertFalse(r["still_before_60_minute_precommit_deadline"])
        self.assertEqual(r["reason"], "CANNOT_RETROACTIVELY_CREATE_FORECAST")
        self.assert_no_go(r)

    def test_exact_60_minute_deadline_is_last_permitted_inspection_in_lab(self):
        deadline = datetime(2026, 11, 8, 21, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(
            audit(inspected=deadline)["state"],
            "LAB_COHORT_STRUCTURE_VALID_BEFORE_DEADLINE_NO_FORECAST")

    def test_one_unfilled_slot_removed_must_be_rejected(self):
        p = json.loads(raw())
        p["slots"].pop()
        self.assertEqual(audit(json.dumps(p).encode())["state"], "LAB_BLOCKED")
        self.assert_no_go(audit(json.dumps(p).encode()))

    def test_reordered_slots_cannot_select_winners_later(self):
        p = json.loads(raw())
        p["slots"][:2] = list(reversed(p["slots"][:2]))
        r = audit(json.dumps(p, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "FROZEN_56_SLOT_UNIVERSE_OR_CANONICAL_BYTES_CHANGED")

    def test_filled_forecast_or_fake_witness_alters_frozen_manifest(self):
        for field, value in (
            ("direction", "ALTA"),
            ("forecast_receipt_sha256", "b" * 64),
            ("independent_precommit_witness", "pretend signed"),
            ("state", "COMMITTED"),
        ):
            with self.subTest(field=field):
                p = json.loads(raw())
                p["slots"][0][field] = value
                payload = (json.dumps(p, sort_keys=True,
                                      separators=(",", ":")) + "\n").encode()
                r = audit(payload)
                self.assertEqual(r["state"], "LAB_BLOCKED")
                self.assert_no_go(r)

    def test_changed_symbol_horizon_dates_deadline_cannot_pass(self):
        for path, value in (
            (("slots", 10, "pair"), "USD/EUR"),
            (("slots", 11, "horizon"), "W1"),
            (("daily_window", "start_at_utc"), "2026-11-07T22:00:00Z"),
            (("weekly_window", "precommit_deadline_utc"), "2026-11-08T22:00:00Z"),
        ):
            p = json.loads(raw())
            if len(path) == 3:
                p[path[0]][path[1]][path[2]] = value
            else:
                p[path[0]][path[1]] = value
            payload = (json.dumps(p, sort_keys=True,
                                  separators=(",", ":")) + "\n").encode()
            self.assertEqual(audit(payload)["state"], "LAB_BLOCKED")

    def test_deleting_exclusion_policy_for_missing_or_neutral_is_blocked(self):
        for field in ("all_slots_required_in_future_coverage_report",
                      "neutral_is_not_a_directional_hit",
                      "missing_outcomes_cannot_be_treated_as_wins"):
            p = json.loads(raw())
            p["coverage_policy"][field] = False
            payload = (json.dumps(p, sort_keys=True,
                                  separators=(",", ":")) + "\n").encode()
            self.assertEqual(audit(payload)["state"], "LAB_BLOCKED")

    def test_canonical_form_required_to_avoid_ambiguous_commit_bytes(self):
        p = json.loads(raw())
        self.assertEqual(audit(json.dumps(p, indent=2).encode())["state"],
                         "LAB_BLOCKED")
        self.assertEqual(audit(raw()[:-1])["state"], "LAB_BLOCKED")

    def test_future_planning_reference_claim_is_not_accepted(self):
        before = datetime(2026, 11, 6, 13, 49, 59, tzinfo=timezone.utc)
        r = audit(inspected=before)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "INVALID_OR_FUTURE_PLANNING_REFERENCE_CLAIM")

    def test_wrong_utc_clock_or_payload_type_denied(self):
        for when in (None, datetime(2026, 11, 6, 14, 0), "2026-11-06", 42):
            r = audit(inspected=when)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_go(r)
        for payload in (None, {}, "manifest", b"", b"{}", b"bad", b"x"*40001):
            self.assertEqual(audit(payload)["state"], "LAB_BLOCKED")

    def test_october_edt_must_not_use_november_est_offset(self):
        oct_before = datetime(2026, 10, 23, 13, 0, tzinfo=timezone.utc)
        p = build(planning_reference_utc=oct_before)
        self.assertEqual(p["daily_window"]["start_at_utc"],
                         "2026-10-25T21:00:00Z")
        self.assertEqual(p["weekly_window"]["start_at_utc"],
                         "2026-10-25T21:00:00Z")

    def test_all_future_trial_cohort_plans_have_no_trades_or_jobs(self):
        for day in (
            datetime(2026, 11, 6, 13, 50, tzinfo=timezone.utc),
            datetime(2026, 11, 9, 14, 0, tzinfo=timezone.utc),
            datetime(2027, 3, 12, 13, 0, tzinfo=timezone.utc),
        ):
            p = build(planning_reference_utc=day)
            self.assertFalse(p["worker_enabled"])
            self.assertFalse(p["scheduler_enabled"])
            self.assertFalse(p["trade_authorized"])
            self.assertIsNone(p["fx_bias"])
            self.assertEqual(p["validated_prediction_count"], 0)
            self.assertIsNone(p["validated_accuracy"])
            self.assertEqual(p["unfilled_slots"], 56)

    def test_no_network_access_in_generation_or_validation(self):
        p = build(planning_reference_utc=PLANNING_REFERENCE)
        self.assertNotIn("news_fetch", p)
        self.assertEqual(audit()["evaluable_predictions"], 0)
        self.assert_no_go(audit())


if __name__ == "__main__":
    unittest.main()
