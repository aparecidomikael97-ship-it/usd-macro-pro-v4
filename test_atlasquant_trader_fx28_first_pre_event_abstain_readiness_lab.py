"""Synthetic no-source FX28 first D1/W1 abstain readiness contracts."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_macro_pit_forecast_preflight_lab import (
    inspect_fx28_macro_pit_forecast_preflight_lab as preflight,
    _pair_evidence_digest,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import _nominal_windows
from atlasquant_trader_fx28_ny17_forecast_witness_lab import PairForecastClaim
from atlasquant_trader_fx28_first_pre_event_abstain_readiness_lab import (
    inspect_first_fx28_pre_event_abstain_readiness_lab as inspect,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 13, 1, 2, tzinfo=UTC)
CUTOFF = NOW - timedelta(minutes=2)
ISSUED = NOW - timedelta(minutes=1)
MODEL_SHA = sha256(b"TEST_ONLY_ABSTAIN_POLICY_NOT_TRAINED_MODEL").hexdigest()


def first_two_reports():
    # Deliberately zero user-supplied issuer receipts and zero original bytes.
    # This is NOT evidence that real official data do not exist.
    receipts = {currency: [] for currency in CURRENCIES}
    originals = {currency: {} for currency in CURRENCIES}
    reports = {}
    for horizon in ("D1", "W1"):
        start, end = _nominal_windows(horizon)[0]
        forecasts = tuple(PairForecastClaim(
            pair=pair, direction="ABSTAIN", abstain_reason="MISSING_MACRO",
            feature_cutoff_at=CUTOFF, forecast_issued_at=ISSUED,
            model_sha256_claim=MODEL_SHA,
            evidence_sha256_claim=_pair_evidence_digest(
                pair=pair, horizon=horizon, cutoff=CUTOFF,
                receipts_by_currency=receipts,
                raw_source_bytes_by_currency=originals,
            ),
        ) for pair in OFFICIAL_PAIRS)
        reports[horizon] = preflight(
            horizon=horizon,
            window_start_at=start, window_end_at=end,
            feature_cutoff_at=CUTOFF, prepared_at=NOW,
            receipts_by_currency=receipts,
            raw_source_bytes_by_currency=originals,
            forecast_roster=forecasts,
        )
        assert reports[horizon]["all_28_forecasts_locally_reconciled"], reports[horizon]
    return reports


def snapshot_from_report(report, *, comment_id=190600):
    return {
        "id": comment_id,
        "url": "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4"
               f"/issues/1884#issuecomment-{comment_id}",
        "body": report["anchor_comment_body_unposted"],
        "created_at": None,
        "updated_at": None,
    }


class FirstAbstainReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good = first_two_reports()

    def check(self, *, reports=None, comments=None, now=NOW):
        return inspect(
            preflight_reports_by_horizon=(
                deepcopy(self.good) if reports is None else reports),
            github_issue_comment_snapshots=[] if comments is None else comments,
            inspected_at_utc=now,
        )

    def safety(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["directional_bias"])
        self.assertIsNone(result["directional_probability"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["forecast_accuracy_validated"])
        self.assertFalse(result["pre_event_witness_independently_attested"])
        self.assertFalse(result["github_comment_created_at_independently_authenticated"])
        self.assertFalse(result["original_macro_source_issuer_authenticated"])
        self.assertFalse(result["macro_first_release_timestamp_attested"])
        self.assertFalse(result["broker_m15_history_point_in_time_authenticated"])
        self.assertFalse(result["native_w1_used_as_ny17_label"])
        self.assertFalse(result["canonical_bytes_independently_retained"])
        self.assertEqual(result["files_written"], 0)
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["new_cost_brl"], 0)

    def test_both_dry_run_28_pair_abstain_rosters_stay_unposted(self):
        r = self.check()
        self.safety(r)
        self.assertEqual(
            r["state"], "LAB_FIRST_FX28_ABSTAIN_PREPARED_BUT_NOT_POSTED_NO_GO")
        self.assertEqual(r["prepared_dry_run_abstentions"], 56)
        self.assertEqual(r["expected_pair_horizon_slots"], 56)
        self.assertEqual(r["directional_forecasts"], 0)
        self.assertEqual(r["comment_body_matches_found"], 0)
        self.assertEqual(
            r["horizon_details"]["D1"]["github_comment_status"], "PREPARED_UNPOSTED")
        self.assertEqual(
            r["horizon_details"]["W1"]["github_comment_status"], "PREPARED_UNPOSTED")
        self.assertEqual(
            r["horizon_details"]["D1"]["start_utc"], "2026-11-15T22:00:00+00:00")

    def test_realistic_existing_issue_note_is_not_a_forecast_commitment(self):
        comments = [{
            "id": 6840355769,
            "url": "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4"
                   "/issues/1884#issuecomment-6840355769",
            "body": "Aviso pré-campanha: gaps domingo NY17; nenhum viés",
            "created_at": None, "updated_at": None,
        }]
        r = self.check(comments=comments)
        self.safety(r)
        self.assertEqual(r["comment_body_matches_found"], 0)
        self.assertEqual(r["prepared_dry_run_abstentions"], 56)
        self.assertEqual(r["state"],
                         "LAB_FIRST_FX28_ABSTAIN_PREPARED_BUT_NOT_POSTED_NO_GO")

    def test_matching_comment_without_github_timestamps_not_witnessed(self):
        c = snapshot_from_report(self.good["D1"])
        r = self.check(comments=[c])
        self.safety(r)
        self.assertEqual(r["comment_body_matches_found"], 1)
        self.assertEqual(r["matching_comments_with_missing_timestamps"], 1)
        self.assertEqual(
            r["horizon_details"]["D1"]["github_comment_status"],
            "COMMENT_EXISTS_BUT_SERVER_TIMESTAMPS_UNAVAILABLE",
        )
        self.assertEqual(r["horizon_details"]["W1"]["github_comment_status"],
                         "PREPARED_UNPOSTED")

    def test_claimed_early_github_timestamps_are_not_independent_proof(self):
        c = snapshot_from_report(self.good["W1"])
        c["created_at"] = "2026-11-13T00:56:00Z"
        c["updated_at"] = "2026-11-13T00:56:00Z"
        r = self.check(comments=[c])
        self.safety(r)
        self.assertEqual(
            r["horizon_details"]["W1"]["github_comment_status"],
            "COMMENT_FIELDS_CLAIM_PRESTART_UNATTESTED",
        )

    def test_duplicate_matching_github_comments_are_rejected(self):
        c1 = snapshot_from_report(self.good["D1"], comment_id=111)
        c2 = snapshot_from_report(self.good["D1"], comment_id=222)
        r = self.check(comments=[c1, c2])
        self.safety(r)
        self.assertEqual(r["state"], "LAB_FIRST_ABSTAIN_PREFLIGHT_BLOCKED")
        self.assertEqual(r["reason"], "DUPLICATE_WITNESS_COMMENTS_REJECTED")

    def test_comment_from_different_issue_or_forged_id_is_rejected(self):
        for url in (
            "https://github.com/other/repo/issues/1884#issuecomment-123",
            "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/"
            "1905#issuecomment-123",
        ):
            c = snapshot_from_report(self.good["D1"], comment_id=123)
            c["url"] = url
            r = self.check(comments=[c])
            self.safety(r)
            self.assertEqual(r["reason"], "COMMENT_ID_OR_ISSUE_LOCATION_INVALID")

    def test_macro_missing_batch_cannot_be_forged_into_directional(self):
        for field, value in (
            ("directional_claims_research_only", 1),
            ("explicit_abstentions", 27),
            ("macro_missing_or_unverifiable_pairs", 27),
            ("forecast_witnessed_before_session", True),
            ("trade_authorized", True),
        ):
            with self.subTest(field=field):
                reports = deepcopy(self.good)
                reports["D1"][field] = value
                r = self.check(reports=reports)
                self.safety(r)
                self.assertEqual(
                    r["reason"], "NOT_A_28_PAIR_NO_MACRO_ABSTAIN_ONLY_PREFLIGHT")

    def test_edited_roster_canonical_json_or_digest_blocks(self):
        for mode in ("digest", "direction", "missing_pair", "extra_json"):
            with self.subTest(mode=mode):
                reports = deepcopy(self.good)
                packet = reports["W1"]["canonical_forecast_json_unposted"]
                if mode == "digest":
                    reports["W1"]["forecast_roster_sha256_unposted"] = "a"*64
                elif mode == "direction":
                    obj = json.loads(packet)
                    obj["pairs"][0]["direction_claim"] = "UP"
                    packet = json.dumps(
                        obj,sort_keys=True,ensure_ascii=True,separators=(",", ":"))
                    reports["W1"]["canonical_forecast_json_unposted"] = packet
                    reports["W1"]["forecast_roster_sha256_unposted"] = (
                        sha256(packet.encode("ascii")).hexdigest())
                elif mode == "missing_pair":
                    obj = json.loads(packet)
                    obj["pairs"].pop()
                    packet = json.dumps(
                        obj,sort_keys=True,ensure_ascii=True,separators=(",", ":"))
                    reports["W1"]["canonical_forecast_json_unposted"] = packet
                    reports["W1"]["forecast_roster_sha256_unposted"] = (
                        sha256(packet.encode("ascii")).hexdigest())
                else:
                    reports["W1"]["canonical_forecast_json_unposted"] += "\n"
                r = self.check(reports=reports)
                self.safety(r)
                self.assertEqual(
                    r["reason"], "CANONICAL_28_ABSTAIN_JSON_OR_DIGEST_INVALID")

    def test_nonfinite_or_broken_forecast_json_is_rejected_safely(self):
        for payload in (
            '{"payload":NaN}',
            '{"payload":Infinity}',
            '{"payload":-Infinity}',
            '{"pairs":[null]}',
        ):
            with self.subTest(payload=payload):
                reports = deepcopy(self.good)
                reports["D1"]["canonical_forecast_json_unposted"] = payload
                r = self.check(reports=reports)
                self.safety(r)
                self.assertEqual(
                    r["reason"], "CANONICAL_28_ABSTAIN_JSON_OR_DIGEST_INVALID")

    def test_horizon_swapped_or_first_window_shifted_blocks(self):
        reports = deepcopy(self.good)
        reports["W1"], reports["D1"] = reports["D1"], reports["W1"]
        r = self.check(reports=reports)
        self.safety(r)
        self.assertEqual(r["reason"], "NOT_A_28_PAIR_NO_MACRO_ABSTAIN_ONLY_PREFLIGHT")
        reports = deepcopy(self.good)
        reports["W1"]["window_end_utc"] = "2026-11-21T00:00:00+00:00"
        r = self.check(reports=reports)
        self.safety(r)
        self.assertEqual(r["reason"], "NOT_A_28_PAIR_NO_MACRO_ABSTAIN_ONLY_PREFLIGHT")

    def test_after_first_window_start_cannot_republish_pre_event(self):
        r = self.check(now=datetime(2026, 11, 15, 22, tzinfo=UTC))
        self.safety(r)
        self.assertEqual(r["reason"], "FIRST_NY17_SESSION_STARTED_CANNOT_PREPARE_NOW")
        self.assertEqual(r["prepared_dry_run_abstentions"], 0)

    def test_null_or_naive_clock_comments_and_oversized_rejected(self):
        for now in (None, NOW.replace(tzinfo=None)):
            r = self.check(now=now)
            self.safety(r)
            self.assertEqual(r["state"], "LAB_FIRST_ABSTAIN_PREFLIGHT_BLOCKED")
        c = snapshot_from_report(self.good["D1"])
        c["body"] = "x"*16_001
        r = self.check(comments=[c])
        self.safety(r)
        self.assertEqual(r["reason"], "COMMENT_BODY_INVALID_OR_OVERSIZED")

    def test_matching_comment_future_or_incoherent_timestamp_cannot_pass(self):
        for creation, updated in (
            ("2026-11-13T01:03:00Z", "2026-11-13T01:03:00Z"),
            ("2026-11-13T00:57:00Z", "2026-11-13T00:50:00Z"),
            ("wrong", "wrong"),
        ):
            with self.subTest(creation=creation):
                c = snapshot_from_report(self.good["D1"])
                c["created_at"] = creation
                c["updated_at"] = updated
                r = self.check(comments=[c])
                self.safety(r)
                self.assertEqual(
                    r["reason"], "COMMENT_SERVER_TIMESTAMP_CLAIMS_INCOHERENT")


if __name__ == "__main__":
    unittest.main()
