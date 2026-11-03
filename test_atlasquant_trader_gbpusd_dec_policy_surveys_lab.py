"""Real documentary surveys for December 2026, never GBP/USD signals."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from atlasquant_trader_gbpusd_dec_policy_surveys_lab import (
    SCHEMA, compare_gbpusd_dec2026_policy_surveys_lab,
)

CASE = (Path(__file__).resolve().parent / "docs" / "continuidade"
        / "TRADER_GBPUSD_DEC2026_SURVEY_PAIR_FREEZE_20261103.json")
BEFORE_EVENTS = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
FIRST_EVENT_DAY = datetime(2026, 12, 9, 12, tzinfo=timezone.utc)


def book():
    return json.loads(CASE.read_text(encoding="utf-8"))


def evaluate(raw=None, when=BEFORE_EVENTS):
    return compare_gbpusd_dec2026_policy_surveys_lab(
        book() if raw is None else raw, evaluated_at=when,
    )


class GBPUSDDecemberSurveyPairTests(unittest.TestCase):
    def test_pre_event_december_surveys_are_documented_only(self):
        out = evaluate()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "LAB_STALE_DOCUMENTARY_DEC_POLICY_PAIR_ONLY")
        self.assertEqual(out["gbp_survey_median_pct"], "3.75")
        self.assertEqual(out["usd_survey_median_pct"], "3.63")
        self.assertTrue(out["old_samples_exceed_30_day_policy"])

    def test_different_releasing_panels_preserved(self):
        d = book()
        self.assertEqual(d["boe"]["respondents"], 92)
        self.assertEqual(d["nyfed"]["respondents"], 62)
        self.assertEqual(d["boe"]["target_event_on"], "2026-12-17")
        self.assertEqual(d["nyfed"]["target_event_on"], "2026-12-09")

    def test_fed_range_midpoint_not_boE_rate(self):
        d = book()
        self.assertIn("TARGET_RANGE_MIDPOINT", d["nyfed"]["survey_measure"])
        self.assertIn("BANK_RATE", d["boe"]["survey_measure"])

    def test_nyfed_publication_day_not_invented(self):
        d = book()
        self.assertIsNone(d["nyfed"]["published_on"])
        self.assertFalse(d["publication_timestamps_independently_attested"])

    def test_boe_has_september_publication_day(self):
        self.assertEqual(book()["boe"]["published_on"], "2026-09-18")

    def test_source_identity_matches_boe_and_nyfed(self):
        d = book()
        self.assertTrue(d["boe"]["source_url"].startswith(
            "https://www.bankofengland.co.uk/"))
        self.assertTrue(d["nyfed"]["source_url"].startswith(
            "https://www.newyorkfed.org/"))

    def test_first_documentary_day_does_not_claim_time_custody(self):
        out = evaluate(when=datetime(2026, 11, 3, 23, 59, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_next_utc_day_is_conservative_first_eligibility(self):
        out = evaluate(when=datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_STALE_DOCUMENTARY_DEC_POLICY_PAIR_ONLY")

    def test_event_day_blocks_past_survey_as_prospective(self):
        out = evaluate(when=FIRST_EVENT_DAY)
        self.assertEqual(out["state"], "LAB_DEC_POLICY_PAIR_TARGET_PASSED")
        self.assertIsNone(out["gbp_survey_median_pct"])
        self.assertIsNone(out["usd_survey_median_pct"])

    def test_after_first_event_also_blocks(self):
        out = evaluate(when=datetime(2026, 12, 18, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_DEC_POLICY_PAIR_TARGET_PASSED")

    def test_naive_evaluation_blocked(self):
        with self.assertRaises(ValueError):
            evaluate(when=datetime(2026, 11, 4))

    def test_timezone_conversion_preserves_utc_cutoff(self):
        time = datetime.fromisoformat("2026-11-03T20:30:00-04:00")
        self.assertEqual(evaluate(when=time)["state"],
                         "LAB_STALE_DOCUMENTARY_DEC_POLICY_PAIR_ONLY")

    def test_forged_published_us_date_rejected(self):
        d = book()
        d["nyfed"]["published_on"] = "2026-09-17"
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_retroactive_relabel_of_source_rejected(self):
        d = book()
        d["nyfed"]["source_url"] = "https://www.newyorkfed.org/false"
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_survey_midpoint_relabelled_to_ois_rejected(self):
        d = book()
        d["nyfed"]["survey_measure"] = "USD_OIS_IMPLIED_RATE"
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_changed_usd_median_rejected(self):
        d = book()
        d["nyfed"]["median_pct"] = "3.88"
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_float_median_rejected(self):
        d = book()
        d["boe"]["median_pct"] = 3.75
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_nonsense_probability_attestation_rejected(self):
        d = book()
        d["real_oos_verified"] = True
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_claim_of_raw_pdf_custody_rejected(self):
        d = book()
        d["source_pdf_bytes_archived"] = True
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_claim_of_earlier_first_observed_rejected(self):
        d = book()
        d["first_lab_observed_on"] = "2026-09-09"
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_changed_freshness_rule_rejected(self):
        d = book()
        d["survey_freshness_days"] = 500
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_hidden_trade_signal_rejected(self):
        d = book()
        d["buy_gbpusd"] = True
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_missing_survey_field_rejected(self):
        d = book()
        del d["nyfed"]["p25_pct"]
        self.assertEqual(evaluate(d)["state"], "LAB_POLICY_PAIR_REFUSED")

    def test_survey_as_live_consensus_always_false(self):
        for now in (BEFORE_EVENTS, FIRST_EVENT_DAY):
            self.assertFalse(evaluate(when=now)["survey_as_live_consensus"])

    def test_rate_gap_is_never_calculated(self):
        out = evaluate()
        self.assertIsNone(out["nominal_rate_gap_pp"])
        self.assertIsNone(out["implied_rate_path_spread_bp"])

    def test_no_operational_implication(self):
        for now in (BEFORE_EVENTS, FIRST_EVENT_DAY):
            out = evaluate(when=now)
            self.assertEqual(out["fx_bias"], "AGUARDAR")
            self.assertIsNone(out["fx_probability"])
            self.assertFalse(out["accuracy_90_proven"])
            self.assertFalse(out["trade_authorized"])
            self.assertFalse(out["can_feed_live_radar"])
            self.assertFalse(out["worker_enabled"])
            self.assertFalse(out["scheduler_enabled"])

    def test_snapshot_hash_not_source_authentication(self):
        out = evaluate()
        self.assertEqual(len(out["snapshot_sha256"]), 64)
        self.assertFalse(out["independent_point_in_time_receipt"])
        self.assertFalse(out["walk_forward_oos_verified"])


if __name__ == "__main__":
    unittest.main()
