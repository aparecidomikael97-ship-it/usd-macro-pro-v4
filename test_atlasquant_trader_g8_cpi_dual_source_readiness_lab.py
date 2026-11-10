"""USD/EUR CPI readiness tests with fabricated BLS API responses only."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_cpi_dual_source_readiness_lab import (
    inspect_g8_cpi_dual_source_readiness_lab as inspect,
)
from test_atlasquant_trader_g8_cpi_bilateral_coverage_lab import fixture as eur_fixture
from test_atlasquant_trader_us_bls_cpi_snapshot_asof_lab import receipt
from test_atlasquant_trader_us_bls_cpi_yoy_snapshot_lab import data_row, payload

AFTER = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)
BEFORE = datetime(2026, 11, 9, 23, 59, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
AFTER_OCTOBER_RELEASE = datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)


def postrelease_october_receipt(raw):
    rec = receipt(raw)
    rec["local_started_utc_claim"] = "2026-11-10T13:30:00Z"
    rec["local_finished_utc_claim"] = "2026-11-10T13:30:00Z"
    return rec


def run(*, docs=None, raw=None, rec=None, month="2026-09", horizon="D1",
        decision=AFTER, evaluated=LATER):
    docs = eur_fixture() if docs is None else docs
    raw = payload() if raw is None else raw
    rec = receipt(raw) if rec is None else rec
    return inspect(docs, usd_raw_response=raw, usd_receipt=rec,
                   usd_reference_period=month, horizon=horizon,
                   decision_at_utc=decision, evaluated_at_utc=evaluated)


class DualSourceCPIReadinessLabTests(unittest.TestCase):
    def no_go(self, r):
        for key in ("usd_source_authenticated", "eur_source_first_release_authenticated",
                    "eur_hicp_us_cpi_u_methodology_harmonized",
                    "country_inflation_rate_difference_directionally_interpretable",
                    "historical_point_in_time_verified",
                    "two_sided_macro_comparison_allowed",
                    "publishable", "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertIs(r[key], False, key)
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["score_0_to_10"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))

    def blocked(self, r, reason):
        self.assertEqual(r["state"], "LAB_DUAL_CPI_READINESS_BLOCKED")
        self.assertEqual(r["reason"], reason)
        self.assertIsNone(r["usd_derived_yoy_claim_research_only"])
        self.no_go(r)

    def test_eur_and_usd_synthetic_candidate_are_not_two_eligible_sources(self):
        r = run()
        self.assertEqual(r["state"], "LAB_EUR_DOCUMENT_USD_API_CANDIDATE_ONLY_NO_BIAS")
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual(set(r["pairs"]), set(OFFICIAL_PAIRS))
        self.assertEqual(r["eur_documentary_crosses"], 7)
        self.assertEqual(r["usd_parser_candidate_crosses"], 7)
        self.assertEqual(r["eur_usd_dual_pipeline_candidates"], 1)
        self.assertEqual(r["two_documented_pairs"], 0)
        self.assertEqual(r["eur_reference_period_claim"], "2026-10")
        self.assertEqual(r["usd_reference_period_claim"], "2026-09")
        self.assertFalse(r["same_reference_period_for_eur_usd"])
        self.assertTrue(r["usd_response_hash_self_consistent"])
        self.assertEqual(r["usd_derived_yoy_claim_research_only"], "5.000")
        self.assertTrue(r["pairs"]["EUR/USD"]["combined_eur_usd_candidate_only"])
        self.no_go(r)

    def test_every_pair_stays_aguarar_and_has_no_macro_direction(self):
        r = run()
        for pair, item in r["pairs"].items():
            self.assertEqual(item["operational_bias"], "AGUARDAR", pair)
            self.assertIs(item["two_sided_macro_comparison_allowed"], False, pair)
            self.assertIsNone(item["economic_strength_direction"], pair)
            self.assertIs(item["trade_authorized"], False, pair)
        self.no_go(r)

    def test_october_period_alignment_cannot_invent_missing_us_year_ago_index(self):
        # BLS 10 Nov 2026 October release: Oct 2025 CPI-U index unavailable.
        # Matching the EUR reference month must not hide this missing year-ago value.
        raw = payload([data_row(2026, 10, "320"), data_row(2025, 10, "310")])
        r = run(raw=raw, rec=postrelease_october_receipt(raw),
                month="2026-10", decision=AFTER_OCTOBER_RELEASE)
        self.blocked(r, "USD_BLS_BYTES_RECEIPT_OR_PERIOD_INVALID")

    def test_october_2026_receipt_claim_before_0830_est_is_not_eligible(self):
        self.blocked(run(month="2026-10", decision=AFTER_OCTOBER_RELEASE),
                     "USD_CAPTURE_CLAIM_BEFORE_KNOWN_BLS_RELEASE")

    def test_after_cutoff_capture_is_blocked_not_backfilled(self):
        self.blocked(run(decision=BEFORE), "USD_CAPTURE_AFTER_DECISION_NO_LOOKAHEAD")

    def test_current_or_future_month_injected_into_past_decision_rejected(self):
        for month in ("2026-11", "2026-12", "2027-01"):
            with self.subTest(month=month):
                self.blocked(run(month=month),
                             "USD_MONTHLY_OBSERVATION_NOT_YET_ENDED_AT_DECISION")

    def test_missing_homologous_index_level_blocks_even_with_hash(self):
        raw = payload()
        r = run(raw=raw, rec=postrelease_october_receipt(raw),
                month="2026-10", decision=AFTER_OCTOBER_RELEASE)
        self.blocked(r, "USD_BLS_BYTES_RECEIPT_OR_PERIOD_INVALID")

    def test_api_hash_tampering_or_wrong_source_refuses(self):
        raw = payload()
        bad = receipt(raw)
        bad["body_sha256"] = "0" * 64
        self.blocked(run(raw=raw, rec=bad), "USD_BLS_BYTES_RECEIPT_OR_PERIOD_INVALID")
        self.blocked(run(raw=payload(series_id="FAKE_SERIES")),
                     "USD_BLS_BYTES_RECEIPT_OR_PERIOD_INVALID")

    def test_non_euro_unvalidated_document_still_rejected(self):
        docs = eur_fixture()
        docs["GBP"] = deepcopy(docs["EUR"])
        self.blocked(run(docs=docs), "INVALID_SOURCE_COVERAGE_OR_EVALUATION_TIME")

    def test_eur_claims_of_broker_or_issuer_attestation_fail_closed(self):
        docs = eur_fixture()
        docs["EUR"]["issuer_first_release_authenticated"] = True
        self.blocked(run(docs=docs), "INVALID_SOURCE_COVERAGE_OR_EVALUATION_TIME")

    def test_without_euro_document_only_usd_parser_candidate(self):
        docs = eur_fixture(include_eur=False)
        r = run(docs=docs)
        self.assertEqual(r["eur_documentary_crosses"], 0)
        self.assertEqual(r["usd_parser_candidate_crosses"], 7)
        self.assertEqual(r["eur_usd_dual_pipeline_candidates"], 0)
        self.assertFalse(r["pairs"]["EUR/USD"]["combined_eur_usd_candidate_only"])
        self.no_go(r)

    def test_horizon_monthly_is_coverage_only_not_monthly_prediction(self):
        r = run(horizon="M1")
        self.assertEqual(r["state"], "LAB_EUR_DOCUMENT_USD_API_CANDIDATE_ONLY_NO_BIAS")
        self.no_go(r)

    def test_unsupported_horizon_and_invalid_utc_clock_fail_closed(self):
        self.blocked(run(horizon="M15"), "INVALID_SOURCE_COVERAGE_OR_EVALUATION_TIME")
        self.blocked(run(decision=datetime(2026, 11, 10, 3)),
                     "INVALID_SOURCE_COVERAGE_OR_EVALUATION_TIME")
        self.blocked(run(decision=LATER, evaluated=AFTER),
                     "INVALID_SOURCE_COVERAGE_OR_EVALUATION_TIME")

    def test_duplicate_api_monthly_rows_are_not_research_candidate(self):
        raw = payload([data_row(2026, 9, "315"), data_row(2025, 9, "300"),
                       data_row(2026, 9, "315")])
        self.blocked(run(raw=raw), "USD_BLS_BYTES_RECEIPT_OR_PERIOD_INVALID")

    def test_source_inputs_remain_unchanged(self):
        docs = eur_fixture()
        raw = payload()
        rec = receipt(raw)
        before = deepcopy((docs, rec))
        _ = run(docs=docs, raw=raw, rec=rec)
        self.assertEqual((docs, rec), before)


if __name__ == "__main__":
    unittest.main()
