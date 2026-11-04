"""All Copom/B3 evidence readiness fixtures are fabricated LAB examples.

No true Nov 4 decision, tick, latency, trading result or source license is
contained in these tests. Original pre-event JSON comes from frozen Git blob.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import unittest

from atlasquant_trader_copom_evidence_readiness_lab import (
    SCHEMA, PENDING, CANDIDATES, DENIED, MISSING_EVIDENCE,
    build_copom_evidence_readiness_lab as readiness,
)

PATH = (Path(__file__).resolve().parent / "docs" / "continuidade"
        / "TRADER_COPOM_20261104_FROZEN_PRE_EVENT_20261103.json")
NOV3 = datetime(2026, 11, 3, 18, tzinfo=timezone.utc)
NOV5 = datetime(2026, 11, 5, 13, tzinfo=timezone.utc)

_HEADER = ("instrument,contract_id,session_role,quote_type,"
           "observed_at_utc,price_points\n")


def frozen() -> bytes:
    return PATH.read_bytes()


def report(b=None, *, at=NOV3, policy=None, csv=None, manifest=None):
    return readiness(
        frozen() if b is None else b, evaluated_at=at,
        claimed_bcb_result=policy, price_export_csv=csv,
        price_export_manifest=manifest,
    )


def pretend_release(rate="13.75"):
    text = (f"DOCUMENTO FICTÍCIO DE TESTE: Copom e Selic {rate.replace('.', ',')}%"
            " ao ano, este conteúdo NÃO é a decisão oficial.").encode("utf-8")
    return {
        "source_type": "OFFICIAL_BCB_TEXT_EXTRACT_UNATTESTED",
        "source_name": "BANCO_CENTRAL_DO_BRASIL",
        "source_url": "https://www.bcb.gov.br/controleinflacao/comunicadoscopom/synthetic-test",
        "content_type": "text/plain; charset=utf-8",
        "http_status_claim": 200,
        "declared_published_at_utc": "2026-11-04T21:35:00Z",
        "claimed_first_seen_at_utc": "2026-11-04T21:36:00Z",
        "policy_rate_claim_pct": rate,
        "raw_release_text": text,
        "raw_release_sha256": sha256(text).hexdigest(),
    }


def pretend_prices(*, synthetic=True, instrument="WIN") -> bytes:
    sym = (f"SIM_{instrument}_FAKE_SINGLE_EXPIRY" if synthetic
           else f"{instrument}Z26")
    kind = ("SIMULATED_REGULAR_TRADE_TICK" if synthetic
            else "PROVIDER_DECLARED_EXECUTED_TRADE_UNVERIFIED")
    close = "2026-11-04T21:24:00Z" if instrument == "WIN" else "2026-11-04T21:29:00Z"
    first, second = ("160000", "162000") if instrument == "WIN" else ("5500", "5540")
    rows = [
        f"{instrument},{sym},PRE_20261104,{kind},{close},{first}\n",
        f"{instrument},{sym},POST_20261105,{kind},2026-11-05T12:03:00Z,{second}\n",
    ]
    return (_HEADER + "".join(rows)).encode("utf-8")


def pretend_manifest(prices: bytes, *, synthetic=True) -> dict:
    return {
        "schema": "ATLASQUANT_TRADER_B3_OFFLINE_USER_EXPORT_INTAKE_LAB_V1",
        "declared_collection_method": (
            "SYNTHETIC_FIXTURE" if synthetic
            else "USER_MANUAL_EXPORT_UNVERIFIED"),
        "declared_origin_label": (
            "SYNTHETIC LOCAL TEST" if synthetic
            else "USER FILE UNVERIFIED"),
        "declared_source_reference": "USER_NOTE:synthetic-unauthenticated-test",
        "declared_rights_status": "NOT_INDEPENDENTLY_REVIEWED",
        "collection_was_automated": False,
        "csv_sha256": sha256(prices).hexdigest(),
        "fixture_mode": synthetic,
    }


class CopomEvidenceReadinessLabTests(unittest.TestCase):
    def test_before_decision_is_pending_with_four_provenance_rows(self):
        r = report()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], PENDING)
        self.assertTrue(r["pre_event_source_content_matches_original"])
        self.assertEqual(r["decision_status"], "NO_AUTHENTICATED_RESULT")
        self.assertEqual(r["quote_status"], "NO_AUTHENTICATED_PRICE_DATA")
        self.assertEqual(r["session_status"], "REGULAR_HOURS_DOCUMENTARY_ONLY")
        self.assertEqual(len(r["audit_rows"]), 4)

    def test_missing_independent_evidence_is_explicit_and_stable(self):
        r = report()
        self.assertEqual(r["missing_independent_evidence"], list(MISSING_EVIDENCE))
        self.assertEqual(len(r["missing_independent_evidence"]), 7)
        self.assertIn("ATTEST_ORIGINAL_BCB_COMMUNIQUE_AND_RELEASE_TIME",
                      r["missing_independent_evidence"])

    def test_outcome_is_not_inferred_from_frozen_reuters_poll(self):
        r = report()
        self.assertIsNone(r["decision_candidate_scenario"])
        self.assertFalse(r["outcome_rate_independently_verified"])
        self.assertFalse(r["trader_directional_forecast_pre_registered"])

    def test_after_event_without_source_still_pending(self):
        r = report(at=NOV5)
        self.assertEqual(r["state"], PENDING)
        self.assertEqual(r["decision_status"], "NO_AUTHENTICATED_RESULT")
        self.assertFalse(r["market_session_gap_verified"])

    def test_exact_original_git_bytes_are_required(self):
        altered = json.loads(frozen())
        altered["reuters_poll_hold_responses"] = 48
        self.assertEqual(report(json.dumps(altered).encode())["state"], DENIED)

    def test_same_json_reformatted_is_not_original_checkpoint(self):
        same_values = json.dumps(json.loads(frozen()), indent=4, sort_keys=True).encode()
        self.assertEqual(report(same_values)["state"], DENIED)

    def test_invalid_frozen_source_without_bytes_refused(self):
        for content in ({}, b"", b"{}", [], "snapshot"):
            with self.subTest(type=str(type(content))):
                self.assertEqual(report(content)["state"], DENIED)
        self.assertEqual(readiness(None, evaluated_at=NOV3)["state"], DENIED)

    def test_naive_date_rejected(self):
        with self.assertRaises(ValueError):
            report(at=datetime(2026, 11, 3, 18))

    def test_backdating_before_research_cutoff_denied(self):
        early = datetime(2026, 11, 2, 18, tzinfo=timezone.utc)
        self.assertEqual(report(at=early)["state"], DENIED)

    def test_fake_result_before_official_window_is_refused(self):
        r = report(at=NOV3, policy=pretend_release())
        self.assertEqual(r["state"], DENIED)
        self.assertFalse(r["pre_event_source_content_matches_original"])

    def test_fake_official_communique_candidate_remains_unauthenticated(self):
        r = report(at=NOV5, policy=pretend_release("13.75"))
        self.assertEqual(r["state"], CANDIDATES)
        self.assertEqual(r["decision_status"], "CALLER_SUPPLIED_BCB_CANDIDATE_UNATTESTED")
        self.assertEqual(r["decision_candidate_scenario"], "HOLD_13_75")
        self.assertFalse(r["outcome_rate_independently_verified"])
        self.assertFalse(r["bcb_release_time_independently_verified"])

    def test_fake_cut_scenario_is_not_a_market_prediction(self):
        r = report(at=NOV5, policy=pretend_release("13.50"))
        self.assertEqual(r["state"], CANDIDATES)
        self.assertEqual(r["decision_candidate_scenario"], "CUT_25BP_13_50")
        self.assertFalse(r["trader_predictive_accuracy_proven"])

    def test_fake_other_policy_scenario_is_never_trade_signal(self):
        r = report(at=NOV5, policy=pretend_release("14.00"))
        self.assertEqual(r["state"], CANDIDATES)
        self.assertEqual(r["decision_candidate_scenario"], "OTHER")
        self.assertEqual(r["win_wdo_direction"], "AGUARDAR")

    def test_invalid_outcome_claim_denies_entire_readiness_report(self):
        claim = pretend_release()
        claim["actual_policy_independently_verified"] = True
        self.assertEqual(report(at=NOV5, policy=claim)["state"], DENIED)

    def test_partial_price_export_with_no_rights_manifest_refused(self):
        csv = pretend_prices()
        self.assertEqual(report(at=NOV5, csv=csv)["state"], DENIED)

    def test_manifest_without_csv_refused(self):
        sample = pretend_prices()
        self.assertEqual(report(at=NOV5, manifest=pretend_manifest(sample))["state"], DENIED)

    def test_fake_win_csv_never_counts_as_real_market_evidence(self):
        sample = pretend_prices()
        r = report(at=NOV5, csv=sample, manifest=pretend_manifest(sample))
        self.assertEqual(r["state"], CANDIDATES)
        self.assertEqual(r["quote_status"], "SYNTHETIC_TEST_ONLY")
        self.assertEqual(r["claimed_price_pairs"], 1)
        self.assertFalse(r["market_session_gap_verified"])

    def test_self_declared_manual_export_still_needs_source_license_review(self):
        sample = pretend_prices(synthetic=False)
        r = report(at=NOV5, csv=sample, manifest=pretend_manifest(sample, synthetic=False))
        self.assertEqual(r["state"], CANDIDATES)
        self.assertEqual(r["quote_status"], "MANUAL_EXPORT_CANDIDATE_UNATTESTED")
        self.assertFalse(r["b3_quotes_and_licensing_independently_verified"])
        self.assertFalse(r["economic_causality_proven"])

    def test_future_prices_are_rejected_before_session_even_if_synthetic(self):
        sample = pretend_prices()
        r = report(csv=sample, manifest=pretend_manifest(sample))
        self.assertEqual(r["state"], DENIED)

    def test_forged_price_digest_is_rejected(self):
        sample = pretend_prices()
        m = pretend_manifest(sample)
        m["csv_sha256"] = "0" * 64
        self.assertEqual(report(at=NOV5, csv=sample, manifest=m)["state"], DENIED)

    def test_wrong_contract_in_manually_claimed_prices_denied(self):
        sample = pretend_prices(synthetic=False).replace(b"WINZ26", b"WINX26")
        r = report(at=NOV5, csv=sample,
                   manifest=pretend_manifest(sample, synthetic=False))
        self.assertEqual(r["state"], DENIED)

    def test_synthetic_prices_and_fake_policy_together_still_unattested(self):
        sample = pretend_prices(instrument="WDO")
        r = report(at=NOV5, policy=pretend_release(), csv=sample,
                   manifest=pretend_manifest(sample))
        self.assertEqual(r["state"], CANDIDATES)
        self.assertEqual(r["decision_candidate_scenario"], "HOLD_13_75")
        self.assertEqual(r["quote_status"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(r["market_session_gap_verified"])
        self.assertFalse(r["trade_authorized"])

    def test_no_reused_raw_prices_or_untrusted_text_in_report(self):
        sample = pretend_prices(synthetic=False)
        r = report(at=NOV5, policy=pretend_release(), csv=sample,
                   manifest=pretend_manifest(sample, synthetic=False))
        serialized = str(r)
        self.assertNotIn("160000", serialized)
        self.assertNotIn("162000", serialized)
        self.assertNotIn("synthetic-test", serialized)
        self.assertNotIn("USER_NOTE:", serialized)

    def test_four_rows_stay_unattested_when_every_candidate_is_present(self):
        sample = pretend_prices(synthetic=False)
        r = report(at=NOV5, policy=pretend_release(), csv=sample,
                   manifest=pretend_manifest(sample, synthetic=False))
        self.assertEqual(len(r["audit_rows"]), 4)
        self.assertTrue(all(not x["independently_authenticated"] and
                            not x["usable_as_real_trade_evidence"]
                            for x in r["audit_rows"]))

    def test_all_real_operation_and_accuracy_gates_remain_closed(self):
        sample = pretend_prices(synthetic=False)
        candidates = report(at=NOV5, policy=pretend_release(), csv=sample,
                            manifest=pretend_manifest(sample, synthetic=False))
        for r in (report(), candidates):
            self.assertEqual(r["win_wdo_direction"], "AGUARDAR")
            self.assertFalse(r["economic_causality_proven"])
            self.assertFalse(r["trader_predictive_accuracy_proven"])
            self.assertIsNone(r["market_implied_copom_probability"])
            for field in (
                "outcome_rate_independently_verified",
                "bcb_release_time_independently_verified",
                "b3_schedule_exception_calendar_verified",
                "b3_quotes_and_licensing_independently_verified",
                "market_session_gap_verified",
                "can_feed_live_radar", "can_feed_real_oos",
                "trade_authorized", "worker_enabled", "scheduler_enabled",
                "render_configuration_changed", "paid_provider_approved",
            ):
                self.assertFalse(r[field],field)


if __name__ == "__main__":
    unittest.main()
