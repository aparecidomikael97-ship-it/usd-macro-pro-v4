"""Synthetic vintage chain & first-release consensus LAB integrity checks."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_bias_daily_freeze_lab import (
    freeze_daily_bias_observation_lab,
)
from atlasquant_trader_bias_forecast_bridge_lab import (
    FIXED_METHOD, SCHEMA as BATCH_SCHEMA,
)
from atlasquant_trader_macro_vintages_asof_lab import (
    inspect_macro_vintages_asof_lab,
)

EVAL = datetime(2026, 11, 2, 18, tzinfo=timezone.utc)
FIRST = datetime(2026, 10, 30, 15, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 2, 11, tzinfo=timezone.utc)
BEFORE = datetime(2026, 10, 30, 13, tzinfo=timezone.utc)


def preliminary():
    return {
        "state": "LAB_SYNTHETIC_MACRO_PRE",
        "event_id": "US-CPI-202609",
        "currency": "USD", "indicator_id": "CPI", "unit": "PERCENT",
        "source": "Synthetic consensus research",
        "previous": 2.8,
        "previous_captured_at_utc": "2026-10-29T10:00:00+00:00",
        "consensus": 3.0,
        "consensus_captured_at_utc": "2026-10-30T12:00:00+00:00",
        "scheduled_release_at_utc": "2026-10-30T14:00:00+00:00",
        "deadband_predeclared": 0.05,
    }


def archive():
    return [
        {
            "state": "LAB_SYNTHETIC_MACRO_VINTAGE",
            "event_id": "US-CPI-202609",
            "revision_sequence": 0, "release_stage": "INITIAL",
            "actual": 3.1,
            "released_at_utc": "2026-10-30T14:00:00+00:00",
            "captured_at_utc": "2026-10-30T14:05:00+00:00",
            "source": "Synthetic initial press bulletin",
        },
        {
            "state": "LAB_SYNTHETIC_MACRO_VINTAGE",
            "event_id": "US-CPI-202609",
            "revision_sequence": 1, "release_stage": "REVISED",
            "actual": 2.9,
            "released_at_utc": "2026-11-01T12:00:00+00:00",
            "captured_at_utc": "2026-11-01T12:05:00+00:00",
            "source": "Synthetic official revision bulletin",
        },
    ]


def audit(rows=None, *, pre=None, issued=FIRST, evaluated=EVAL):
    return inspect_macro_vintages_asof_lab(
        preliminary() if pre is None else pre,
        archive() if rows is None else rows,
        forecast_issued_at=issued, evaluated_at=evaluated,
    )


def canonical_daily_batch():
    key = "vintage-lab-1"
    return {
        "schema": BATCH_SCHEMA, "state": "LAB_SYNTHETIC_ISSUED",
        "batch_key": key, "method_id": FIXED_METHOD,
        "issued_at_utc": LATER.isoformat(),
        "forecasts": [
            {
                "forecast_id": f"{key}-{h}-{pair.replace('/', '')}",
                "state": "LAB_SYNTHETIC_BIAS",
                "pair": pair, "horizon": h, "bias": "AGUARDAR",
                "method_id": FIXED_METHOD,
                "issued_at_utc": LATER.isoformat(),
                "evidence_at_utc": "2026-11-02T10:30:00+00:00",
                "trade_authorized": False,
            }
            for pair in OFFICIAL_PAIRS
            for h in ("D1", "W1", "MN1")
        ],
    }


def synthetic_strength():
    return {
        "state": "LAB_SYNTHETIC_EVIDENCE",
        "kind": "G8_STRENGTH_REFERENCE",
        "evidence_id": "g8-vintage-test", "source": "G8 synthetic laboratory",
        "currencies": list(CURRENCIES),
        "data_as_of_utc": "2026-11-02T10:00:00+00:00",
        "captured_at_utc": "2026-11-02T10:30:00+00:00",
    }


class MacroVintageAsOfLabTests(unittest.TestCase):
    def test_original_release_is_selected_before_later_revision(self):
        result = audit()
        self.assertEqual(result["state"], "LAB_SYNTHETIC_VINTAGE_ASOF_CONTEXT")
        self.assertEqual(result["selected_stage"], "INITIAL")
        self.assertEqual(result["selected_revision_sequence"], 0)
        self.assertEqual(result["selected_actual_asof"], 3.1)
        self.assertIsNone(result["revision_context_asof"])
        self.assertEqual(result["forecast_safe_evidence"]["actual"], 3.1)
        self.assertFalse(result["future_revision_values_exposed"])

    def test_revised_asof_is_separate_and_cannot_rewrite_original_actual(self):
        result = audit(issued=LATER)
        self.assertEqual(result["selected_stage"], "REVISED")
        self.assertEqual(result["selected_actual_asof"], 2.9)
        self.assertEqual(result["revision_context_asof"]["revision_sequence"], 1)
        self.assertEqual(result["revision_context_asof"]["initial_actual_unchanged"], 3.1)
        self.assertAlmostEqual(result["revision_context_asof"]["revision_delta_vs_initial"],
                               -0.2)
        self.assertEqual(result["original_release_evidence"]["actual"], 3.1)
        self.assertEqual(result["forecast_safe_evidence"]["actual"], 3.1)
        self.assertFalse(result["revision_context_asof"]["can_feed_as_initial_surprise"])

    def test_first_release_surprise_never_recalculated_using_revision(self):
        initial = audit()
        revised = audit(issued=LATER)
        self.assertAlmostEqual(initial["original_surprise_vs_pre_release_consensus"], 0.1)
        self.assertEqual(initial["original_surprise_vs_pre_release_consensus"],
                         revised["original_surprise_vs_pre_release_consensus"])
        self.assertAlmostEqual(revised["revision_context_asof"]["actual_revised_asof"], 2.9)

    def test_pre_release_forecast_gets_only_schedule_without_actual_or_revisions(self):
        result = audit(issued=BEFORE)
        self.assertEqual(result["state"], "LAB_MACRO_SCHEDULE_ASOF_ONLY")
        self.assertEqual(result["selected_stage"], "SCHEDULE_ONLY")
        self.assertEqual(result["forecast_safe_evidence"]["kind"],
                         "MACRO_SCHEDULE_ONLY")
        self.assertNotIn("actual", result["forecast_safe_evidence"])
        self.assertNotIn("surprise", result["forecast_safe_evidence"])
        self.assertIsNone(result["original_release_evidence"])
        self.assertIsNone(result["revision_context_asof"])

    def test_release_published_but_not_yet_received_is_refused(self):
        result = audit(issued=datetime(2026, 10, 30, 14, 2, tzinfo=timezone.utc))
        self.assertEqual(result["state"], "LAB_MACRO_VINTAGE_REFUSED")
        self.assertIsNone(result["forecast_safe_evidence"])
        self.assertIn("no received value", result["reason"])

    def test_original_capture_at_exact_cutoff_is_allowed(self):
        result = audit(issued=datetime(2026, 10, 30, 14, 5, tzinfo=timezone.utc))
        self.assertEqual(result["state"], "LAB_SYNTHETIC_VINTAGE_ASOF_CONTEXT")
        self.assertEqual(result["selected_stage"], "INITIAL")

    def test_later_revision_after_cutoff_is_not_leaked_backwards(self):
        rows = archive()
        rows.append({
            **rows[-1], "revision_sequence": 2,
            "actual": 2.6,
            "released_at_utc": "2026-11-02T13:00:00+00:00",
            "captured_at_utc": "2026-11-02T13:05:00+00:00",
        })
        result = audit(rows, issued=LATER)
        self.assertEqual(result["selected_stage"], "REVISED")
        self.assertEqual(result["selected_revision_sequence"], 1)
        self.assertEqual(result["selected_actual_asof"], 2.9)
        self.assertFalse(result["future_revision_values_exposed"])

    def test_multiple_revisions_pick_latest_received_not_latest_published(self):
        rows = archive()
        rows.append({
            **rows[-1], "revision_sequence": 2, "actual": 2.7,
            "released_at_utc": "2026-11-02T12:00:00+00:00",
            "captured_at_utc": "2026-11-02T12:04:00+00:00",
        })
        result = audit(rows, issued=LATER)
        self.assertEqual(result["selected_revision_sequence"], 1)
        self.assertEqual(result["selected_actual_asof"], 2.9)
        result_later = audit(rows, issued=datetime(2026, 11, 2, 12, 20,
                                                   tzinfo=timezone.utc))
        self.assertEqual(result_later["selected_revision_sequence"], 2)
        self.assertEqual(result_later["selected_actual_asof"], 2.7)

    def test_missing_original_release_cannot_infer_first_actual(self):
        rows = archive()[1:]
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_first_release_must_have_initial_stage(self):
        rows = archive()
        rows[0]["release_stage"] = "REVISED"
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_later_revision_must_not_pose_as_initial(self):
        rows = archive()
        rows[1]["release_stage"] = "INITIAL"
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_duplicate_or_out_of_order_vintage_sequence_refused(self):
        for sequence in (0, 2, -1, True, "1"):
            rows = archive()
            rows[1]["revision_sequence"] = sequence
            self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_retroactive_revision_timestamp_refused(self):
        for field in ("released_at_utc", "captured_at_utc"):
            rows = archive()
            rows[1][field] = "2026-10-30T14:00:00+00:00"
            self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_revision_captured_before_its_publication_refused(self):
        rows = archive()
        rows[1]["captured_at_utc"] = "2026-11-01T11:59:00+00:00"
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_same_event_identity_required_across_revisions(self):
        rows = archive()
        rows[1]["event_id"] = "UNRELATED-EVENT"
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_first_release_must_match_pre_release_consensus_identity(self):
        rows = archive()
        rows[0]["event_id"] = "UNRELATED-EVENT"
        rows[1]["event_id"] = "UNRELATED-EVENT"
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_missing_previous_or_consensus_cannot_be_recovered_from_revision(self):
        bad = preliminary()
        bad["consensus_captured_at_utc"] = "2026-10-30T15:00:00+00:00"
        self.assertEqual(audit(pre=bad)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_initial_publication_outside_planned_release_window_refused(self):
        rows = archive()
        rows[0]["released_at_utc"] = "2026-10-27T14:00:00+00:00"
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_future_vintage_cannot_exist_after_evaluation_in_archive(self):
        rows = archive()
        rows[1]["released_at_utc"] = "2026-11-03T12:00:00+00:00"
        rows[1]["captured_at_utc"] = "2026-11-03T12:05:00+00:00"
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_non_numeric_or_finite_revision_values_rejected(self):
        for val in (True, None, "2.9", float("nan"),
                    float("inf"), -float("inf"), 10**2000):
            rows = archive()
            rows[1]["actual"] = val
            self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_invalid_source_or_unexpected_hindsight_fields_rejected(self):
        rows = archive()
        rows[1]["future_pair_return"] = -0.25
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")
        rows = archive()
        rows[1]["source"] = ""
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_missing_archive_or_oversized_archive_rejected(self):
        for value in ([], None, {}, archive() * 13):
            self.assertEqual(audit(value)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_timezones_are_mandatory_for_external_clocks_and_receipt(self):
        with self.assertRaises(ValueError):
            audit(issued=datetime(2026, 10, 30, 15))
        with self.assertRaises(ValueError):
            audit(evaluated=datetime(2026, 11, 2, 18))
        rows = archive()
        rows[1]["captured_at_utc"] = "2026-11-01T12:05:00"
        self.assertEqual(audit(rows)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_cannot_evaluate_forecast_after_audit_clock(self):
        later = EVAL + timedelta(hours=1)
        self.assertEqual(audit(issued=later)["state"], "LAB_MACRO_VINTAGE_REFUSED")

    def test_all_permission_and_real_data_attestation_flags_remain_false(self):
        for out in (audit(), audit(issued=LATER), audit(issued=BEFORE)):
            for field in ("real_timestamps_attested",
                          "original_source_attested",
                          "macro_prediction_accuracy_proven",
                          "trade_authorized", "worker_enabled",
                          "scheduler_enabled"):
                self.assertFalse(out[field], field)

    def test_original_evidence_can_be_frozen_without_revision_correction(self):
        out = audit(issued=LATER)
        evidence = [synthetic_strength(), out["forecast_safe_evidence"]]
        frozen = freeze_daily_bias_observation_lab(
            canonical_daily_batch(), evidence, checked_at=EVAL,
        )
        self.assertEqual(frozen["state"], "LAB_FROZEN_SYNTHETIC_OBSERVATION")
        self.assertEqual(frozen["macro_actuals_before_cutoff"], 1)
        self.assertEqual(evidence[1]["actual"], 3.1)
        self.assertFalse(frozen["real_historical_capture_verified"])

    def test_revision_context_cannot_masquerade_as_original_release_evidence(self):
        out = audit(issued=LATER)
        evidence = [synthetic_strength(), out["revision_context_asof"]]
        frozen = freeze_daily_bias_observation_lab(
            canonical_daily_batch(), evidence, checked_at=EVAL,
        )
        self.assertEqual(frozen["state"], "LAB_REJECTED_DAILY_OBSERVATION")

    def test_revisions_do_not_transform_consensus_into_forecast_signals(self):
        out = audit(issued=LATER)
        self.assertFalse(out["revision_context_asof"]["can_feed_macro_veto_directly"])
        self.assertFalse(out["vintage_clock_proven_by_witness"])
        self.assertFalse(out["macro_prediction_accuracy_proven"])


if __name__ == "__main__":
    unittest.main()
